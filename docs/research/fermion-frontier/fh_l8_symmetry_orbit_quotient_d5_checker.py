#!/usr/bin/env python3
"""D5 admissibility and resource gate for a symmetry-orbit Krylov quotient.

This checker proves only that one fixed eight-element, Neel-stabilizing
space/spin action gives a well-defined quotient for the pinned L8 sparse-sector
Krylov prefix through depth three.  It never applies H to the depth-three
vector and therefore cannot bound the degree-six remainder.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import time
import types
from array import array
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Mapping


HERE = Path(__file__).resolve().parent
CONTRACT_ID = "FH-L8-INDEPENDENT-REFERENCE-D5"
PASS_STATUS = "VERIFIED_D5_SYMMETRY_ORBIT_QUOTIENT_ADMISSIBLE_FOR_D6_DESIGN"
SEMANTIC_NO_GO = "NO_GO_D5_SYMMETRY_ORBIT_QUOTIENT_SEMANTICS"
RESOURCE_NO_GO = "NO_GO_D5_SYMMETRY_ORBIT_QUOTIENT_RESOURCE_GATE"
GROUP_ORDER = ("I", "R90", "R180", "R270", "MX", "MY", "MD", "MA")
SHA_RE = re.compile(r"[0-9a-f]{40}")
MASK64 = (1 << 64) - 1
MASK128 = (1 << 128) - 1
_ACTIVE_DEADLINE: float | None = None


class VerificationError(ValueError):
    """A source, semantic, equivalence, or resource invariant failed."""


class SemanticNoGo(Exception):
    """The bound quotient candidate failed a scientific semantic gate."""

    def __init__(self, gate: str, detail: str):
        super().__init__(detail)
        self.gate = gate
        self.detail = detail


class ResourceNoGo(Exception):
    """The bound quotient candidate crossed an internal resource stop."""

    def __init__(self, gate: str, detail: str):
        super().__init__(detail)
        self.gate = gate
        self.detail = detail


def _check_deadline() -> None:
    if _ACTIVE_DEADLINE is not None and time.monotonic() > _ACTIVE_DEADLINE:
        raise ResourceNoGo("internal_wall_deadline", "D5 internal wall deadline exceeded")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _sha_json(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerificationError(f"JSON root must be an object: {path.name}")
    return value


def _validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != CONTRACT_ID:
        raise VerificationError("D5 contract identity drift")
    workload = contract.get("workload")
    expected_workload = {
        "linear_size": 8,
        "boundary": "square_open_boundary_no_wrap",
        "mode_order": "site-major_spin-minor_q=2*(r*L+c)+spin_up0_down1",
        "particle_sector": "N_up=32,N_down=32",
        "neel_basis_hex": "0x66669999666699996666999966669999",
        "audited_krylov_depths": [0, 1, 2, 3],
        "quotient_transition_source_depths": [0, 1, 2],
        "fourth_hamiltonian_action_authorized": False,
    }
    if workload != expected_workload:
        raise VerificationError("D5 workload schema drift")
    group = contract.get("symmetry_group", {})
    if group.get("car_sign_rule") != (
        "(-1)^(inversions_of_site_permutation_on_singly_occupied_sites + "
        "spin_swap*number_of_doublons)"
    ):
        raise VerificationError("D5 CAR sign-rule declaration drift")
    if group.get("observable_character") != {
        "staggered_magnetization": 1,
        "double_occupancy": 1,
    }:
        raise VerificationError("D5 observable character declaration drift")
    limits = contract.get("resource_limits", {})
    expected_limits = {
        "outer_memory_max_bytes": 1_073_741_824,
        "outer_swap_max_bytes": 0,
        "maximum_seconds": 600,
        "max_source_bytes": 1_048_576,
        "max_materialized_states": 2_000_000,
        "max_orbit_representatives": 2_000_000,
        "max_next_action_candidates": 300_000_000,
        "max_audit_group_actions": 16_000_000,
    }
    if limits != expected_limits:
        raise VerificationError("D5 resource-limit schema drift")
    if contract.get("decision_rule") != {
        "protocol_source_or_envelope_failure": "VERIFICATION_FAILED",
        "any_semantic_gate_false": SEMANTIC_NO_GO,
        "any_resource_gate_false": RESOURCE_NO_GO,
        "all_gates_true": PASS_STATUS,
    }:
        raise VerificationError("D5 decision-rule drift")
    if contract.get("parent", {}).get("contract_id") != "FH-L8-INDEPENDENT-REFERENCE-D4":
        raise VerificationError("D5 parent contract declaration drift")
    pins = contract.get("source_pins")
    if (
        not isinstance(pins, list)
        or len(pins) != 3
        or {pin.get("path") for pin in pins}
        != {
            "fh_l8_scalar_supremum_d4_checker.py",
            "fh_l8_scalar_supremum_d4_contract.json",
            "fh_l8_scalar_supremum_d4_result.json",
        }
        or any(set(pin) != {"path", "mode", "blob", "bytes", "sha256"} for pin in pins)
    ):
        raise VerificationError("D5 parent source-pin schema drift")
    chronology = contract.get("chronology", {})
    if (
        chronology.get("official_replay_requires_protocol_commit") is not True
        or chronology.get("result_must_not_exist_in_protocol_commit") is not True
    ):
        raise VerificationError("D5 chronology guard drift")
    expected_coordinates = {
        "stored_value": "canonical_representative_full_basis_per_state_amplitude",
        "orbit_reconstruction": "a[g*r]=fermionic_phase(g,r)*a[r]",
        "inner_product_metric": "diag(orbit_size)",
        "reduced_column_factor": "source_orbit_size/target_orbit_size",
        "metric_hermiticity": "target_orbit_size*T[target,source]=source_orbit_size*T[source,target]",
        "orbit_average_coefficients_used": False,
    }
    if contract.get("quotient_coordinates") != expected_coordinates:
        raise VerificationError("D5 quotient coordinate convention drift")


def _parse_cgroup_limit(value: str, name: str) -> int:
    if value == "max":
        raise VerificationError(f"{name} is unbounded")
    if not value.isdigit():
        raise VerificationError(f"{name} is not a canonical byte limit")
    return int(value)


def _verify_resource_envelope(contract: Mapping[str, Any]) -> dict[str, Any]:
    cgroup_lines = Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines()
    unified = [line.split("::", 1)[1] for line in cgroup_lines if line.startswith("0::")]
    if len(unified) != 1:
        raise VerificationError("unified cgroup v2 path unavailable")
    relative = unified[0].lstrip("/")
    cgroup = Path("/sys/fs/cgroup") / relative
    memory = _parse_cgroup_limit((cgroup / "memory.max").read_text(encoding="ascii").strip(), "memory.max")
    swap = _parse_cgroup_limit((cgroup / "memory.swap.max").read_text(encoding="ascii").strip(), "memory.swap.max")
    limits = contract["resource_limits"]
    if memory != limits["outer_memory_max_bytes"]:
        raise VerificationError("outer memory cap is not the exact frozen value")
    if swap != limits["outer_swap_max_bytes"]:
        raise VerificationError("outer swap cap is not the exact frozen value")
    return {
        "cgroup_v2_enforced": True,
        "memory_max_bytes": memory,
        "memory_swap_max_bytes": swap,
        "internal_deadline_seconds": limits["maximum_seconds"],
        "pass": True,
    }


def _git(*args: str, input_bytes: bytes | None = None) -> bytes:
    root = subprocess.check_output(
        ["git", "-C", str(HERE), "rev-parse", "--show-toplevel"],
        stderr=subprocess.DEVNULL,
    ).decode("ascii").strip()
    return subprocess.check_output(
        ["git", "-C", root, *args], input=input_bytes, stderr=subprocess.DEVNULL
    )


def _verify_protocol_commit(contract: Mapping[str, Any], commit: str) -> dict[str, str]:
    if not isinstance(commit, str) or SHA_RE.fullmatch(commit) is None:
        raise VerificationError("a full protocol commit is required")
    resolved = _git("rev-parse", f"{commit}^{{commit}}").decode("ascii").strip()
    if resolved != commit:
        raise VerificationError("protocol commit is not exact")
    parents = _git("rev-list", "--parents", "-n", "1", commit).decode("ascii").split()
    if len(parents) != 2 or parents[1] != contract["chronology"]["protocol_base_commit"]:
        raise VerificationError("protocol commit parent drift")
    base_tree = _git(
        "rev-parse", f"{contract['chronology']['protocol_base_commit']}^{{tree}}"
    ).decode("ascii").strip()
    if base_tree != contract["chronology"]["protocol_base_tree"]:
        raise VerificationError("protocol base tree drift")
    tree = _git("rev-parse", f"{commit}^{{tree}}").decode("ascii").strip()
    for name in (
        "fh_l8_symmetry_orbit_quotient_d5_checker.py",
        "fh_l8_symmetry_orbit_quotient_d5_contract.json",
    ):
        relative = f"docs/research/fermion-frontier/{name}"
        committed = _git("show", f"{commit}:{relative}")
        if committed != (HERE / name).read_bytes():
            raise VerificationError(f"protocol commit byte drift: {name}")
    result_path = "docs/research/fermion-frontier/fh_l8_symmetry_orbit_quotient_d5_result.json"
    try:
        _git("cat-file", "-e", f"{commit}:{result_path}")
    except subprocess.CalledProcessError:
        pass
    else:
        raise VerificationError("result already exists in protocol commit")
    return {"commit": commit, "tree": tree}


def _verify_parent_sources(contract: Mapping[str, Any]) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    parent = contract["parent"]
    commit = parent["integration_commit"]
    try:
        _git(
            "merge-base",
            "--is-ancestor",
            commit,
            contract["chronology"]["protocol_base_commit"],
        )
    except subprocess.CalledProcessError as exc:
        raise VerificationError("D4 integration is not an ancestor of the protocol base") from exc
    if _git("rev-parse", f"{commit}^{{tree}}").decode("ascii").strip() != parent["integration_tree"]:
        raise VerificationError("D4 integration tree drift")
    loaded: dict[str, bytes] = {}
    for pin in contract["source_pins"]:
        path = HERE / pin["path"]
        if path.resolve().parent != HERE or path.name != pin["path"]:
            raise VerificationError("D4 source pin path escapes the frontier directory")
        raw = path.read_bytes()
        if len(raw) != pin["bytes"] or len(raw) > contract["resource_limits"]["max_source_bytes"]:
            raise VerificationError(f"D4 source byte drift: {path.name}")
        if hashlib.sha256(raw).hexdigest() != pin["sha256"]:
            raise VerificationError(f"D4 source SHA drift: {path.name}")
        line = _git("ls-tree", commit, f"docs/research/fermion-frontier/{pin['path']}").decode("utf-8").strip()
        fields = line.split(None, 3)
        if (
            len(fields) != 4
            or fields[0] != pin["mode"]
            or fields[1] != "blob"
            or fields[2] != pin["blob"]
        ):
            raise VerificationError(f"D4 Git identity drift: {path.name}")
        committed = _git("show", f"{commit}:docs/research/fermion-frontier/{pin['path']}")
        if committed != raw:
            raise VerificationError(f"D4 current/committed bytes differ: {path.name}")
        loaded[path.name] = raw
    d4_contract = json.loads(loaded["fh_l8_scalar_supremum_d4_contract.json"])
    d4_result = json.loads(loaded["fh_l8_scalar_supremum_d4_result.json"])
    if (
        d4_result.get("status") != "VERIFIED_D4_SCALAR_SUPREMUM_CANDIDATE_FAILURE_THRESHOLDS"
        or d4_result.get("verified") is not True
        or d4_result.get("next_branch") != "SYMMETRY_ORBIT_COMPRESSED_SCALAR_KRYLOV"
        or d4_result.get("degree6_remainder_bounded") is not False
    ):
        raise VerificationError("D4 parent authority drift")
    module = types.ModuleType("pinned_fh_l8_d4_for_d5")
    module.__file__ = str(HERE / "fh_l8_scalar_supremum_d4_checker.py")
    exec(compile(loaded["fh_l8_scalar_supremum_d4_checker.py"], module.__file__, "exec"), module.__dict__)
    return module, d4_contract, d4_result


def _compact_even(value: int) -> int:
    value &= int("55" * 16, 16)
    value = (value | (value >> 1)) & int("33" * 16, 16)
    value = (value | (value >> 2)) & int("0f" * 16, 16)
    value = (value | (value >> 4)) & int("00ff" * 8, 16)
    value = (value | (value >> 8)) & int("0000ffff" * 4, 16)
    value = (value | (value >> 16)) & int("00000000ffffffff" * 2, 16)
    value = (value | (value >> 32)) & MASK64
    return value


def _spread_even(value: int) -> int:
    value &= MASK64
    value = (value | (value << 32)) & int("00000000ffffffff" * 2, 16)
    value = (value | (value << 16)) & int("0000ffff" * 4, 16)
    value = (value | (value << 8)) & int("00ff" * 8, 16)
    value = (value | (value << 4)) & int("0f" * 16, 16)
    value = (value | (value << 2)) & int("33" * 16, 16)
    value = (value | (value << 1)) & int("55" * 16, 16)
    return value


def _flip_columns(value: int) -> int:
    value = ((value >> 1) & 0x5555555555555555) | ((value & 0x5555555555555555) << 1)
    value = ((value >> 2) & 0x3333333333333333) | ((value & 0x3333333333333333) << 2)
    return ((value >> 4) & 0x0F0F0F0F0F0F0F0F) | ((value & 0x0F0F0F0F0F0F0F0F) << 4)


def _flip_rows(value: int) -> int:
    value = ((value & 0x00000000FFFFFFFF) << 32) | ((value >> 32) & 0x00000000FFFFFFFF)
    value = ((value & 0x0000FFFF0000FFFF) << 16) | ((value >> 16) & 0x0000FFFF0000FFFF)
    return ((value & 0x00FF00FF00FF00FF) << 8) | ((value >> 8) & 0x00FF00FF00FF00FF)


def _transpose(value: int) -> int:
    temporary = (value ^ (value >> 7)) & 0x00AA00AA00AA00AA
    value ^= temporary ^ (temporary << 7)
    temporary = (value ^ (value >> 14)) & 0x0000CCCC0000CCCC
    value ^= temporary ^ (temporary << 14)
    temporary = (value ^ (value >> 28)) & 0x00000000F0F0F0F0
    return (value ^ temporary ^ (temporary << 28)) & MASK64


def _spatial_images(value: int) -> tuple[int, ...]:
    diagonal = _transpose(value)
    columns = _flip_columns(value)
    rows = _flip_rows(value)
    diagonal_columns = _flip_columns(diagonal)
    return (
        value,
        diagonal_columns,
        _flip_rows(columns),
        _flip_rows(diagonal),
        columns,
        rows,
        diagonal,
        _flip_rows(diagonal_columns),
    )


def _site_target(name: str, row: int, column: int) -> tuple[int, int]:
    edge = 7
    functions = {
        "I": (row, column),
        "R90": (column, edge - row),
        "R180": (edge - row, edge - column),
        "R270": (edge - column, row),
        "MX": (row, edge - column),
        "MY": (edge - row, column),
        "MD": (column, row),
        "MA": (edge - column, edge - row),
    }
    try:
        return functions[name]
    except KeyError as exc:
        raise VerificationError(f"unknown symmetry element: {name}") from exc


def _build_sign_tables(site_permutation: tuple[int, ...]) -> tuple[tuple[bytearray, array], ...]:
    inverse_masks: list[int] = []
    for site, target in enumerate(site_permutation):
        mask = 0
        for later in range(site + 1, 64):
            if site_permutation[later] < target:
                mask |= 1 << later
        inverse_masks.append(mask)
    tables: list[tuple[bytearray, array]] = []
    for block in range(4):
        offset = 16 * block
        end = offset + 16
        later_mask = MASK64 ^ ((1 << end) - 1) if end < 64 else 0
        within = bytearray(1 << 16)
        cross = array("Q", [0]) * (1 << 16)
        for value in range(1, 1 << 16):
            if not (value & 0xFFF):
                _check_deadline()
            bit = value & -value
            index = bit.bit_length() - 1
            previous = value ^ bit
            site = offset + index
            selected_previous = previous << offset
            within[value] = within[previous] ^ ((inverse_masks[site] & selected_previous).bit_count() & 1)
            cross[value] = cross[previous] ^ (inverse_masks[site] & later_mask)
        tables.append((within, cross))
    return tuple(tables)


def _site_subset_permutation_parity(value: int, tables: tuple[tuple[bytearray, array], ...]) -> int:
    parity = 0
    for block, (within, cross) in enumerate(tables):
        word = (value >> (16 * block)) & 0xFFFF
        parity ^= within[word]
        parity ^= (cross[word] & value).bit_count() & 1
    return parity


def _build_symmetries(contract: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    specification = contract["symmetry_group"]
    if tuple(specification["element_order"]) != GROUP_ORDER or specification["expected_order"] != 8:
        raise VerificationError("symmetry group order drift")
    expected_shifts = specification["checkerboard_parity_shift"]
    symmetries: list[dict[str, Any]] = []
    for name in GROUP_ORDER:
        site_permutation = tuple(
            8 * _site_target(name, site // 8, site % 8)[0]
            + _site_target(name, site // 8, site % 8)[1]
            for site in range(64)
        )
        if len(set(site_permutation)) != 64:
            raise VerificationError("site action is not bijective")
        shift_values = {
            ((site_permutation[site] // 8 + site_permutation[site] % 8) - (site // 8 + site % 8)) & 1
            for site in range(64)
        }
        if len(shift_values) != 1:
            raise VerificationError("checkerboard parity shift is not constant")
        shift = shift_values.pop()
        if shift != expected_shifts[name] or specification["spin_swap"][name] != shift:
            raise VerificationError("conditional spin-swap drift")
        mode_permutation = tuple(
            2 * site_permutation[mode // 2] + ((mode & 1) ^ shift) for mode in range(128)
        )
        symmetries.append(
            {
                "name": name,
                "shift": shift,
                "site_permutation": site_permutation,
                "mode_permutation": mode_permutation,
                "sign_tables": _build_sign_tables(site_permutation),
            }
        )
    by_mode_permutation = {item["mode_permutation"]: item["name"] for item in symmetries}
    composition: list[list[str]] = []
    for left in symmetries:
        row: list[str] = []
        for right in symmetries:
            composed = tuple(left["mode_permutation"][right["mode_permutation"][mode]] for mode in range(128))
            if composed not in by_mode_permutation:
                raise VerificationError("mode action is not closed")
            row.append(by_mode_permutation[composed])
        composition.append(row)
    for site in range(64):
        one_hot_images = _spatial_images(1 << site)
        for index, symmetry in enumerate(symmetries):
            if one_hot_images[index] != 1 << symmetry["site_permutation"][site]:
                raise VerificationError("optimized spatial transform drift")
    record = {
        "group_order": 8,
        "element_order": list(GROUP_ORDER),
        "composition_table_sha256": _sha_json(composition),
        "site_permutation_sha256": {
            item["name"]: _sha_json(list(item["site_permutation"])) for item in symmetries
        },
        "mode_permutation_sha256": {
            item["name"]: _sha_json(list(item["mode_permutation"])) for item in symmetries
        },
        "closure_pass": True,
    }
    return symmetries, record


def _generic_mode_action(basis: int, permutation: tuple[int, ...]) -> tuple[int, int]:
    occupied = [mode for mode in range(128) if (basis >> mode) & 1]
    targets = [permutation[mode] for mode in occupied]
    parity = sum(
        targets[left] > targets[right]
        for left in range(len(targets))
        for right in range(left + 1, len(targets))
    ) & 1
    target = 0
    for mode in targets:
        target |= 1 << mode
    return target, -1 if parity else 1


def _basis_images(basis: int, symmetries: list[dict[str, Any]]) -> tuple[tuple[int, int], ...]:
    up = _compact_even(basis)
    down = _compact_even(basis >> 1)
    if (_spread_even(up) | (_spread_even(down) << 1)) != basis:
        raise VerificationError("spin-bitboard round trip failed")
    up_images = _spatial_images(up)
    down_images = _spatial_images(down)
    single = up ^ down
    double = up & down
    double_parity = double.bit_count() & 1
    output: list[tuple[int, int]] = []
    for index, symmetry in enumerate(symmetries):
        if symmetry["shift"]:
            target_up, target_down = down_images[index], up_images[index]
        else:
            target_up, target_down = up_images[index], down_images[index]
        target = _spread_even(target_up) | (_spread_even(target_down) << 1)
        parity = _site_subset_permutation_parity(single, symmetry["sign_tables"])
        parity ^= symmetry["shift"] * double_parity
        output.append((target, -1 if parity else 1))
    return tuple(output)


def _canonical_info(basis: int, symmetries: list[dict[str, Any]]) -> dict[str, Any]:
    images = _basis_images(basis, symmetries)
    phase_by_target: dict[int, int] = {}
    inconsistent = False
    for target, phase in images:
        previous = phase_by_target.setdefault(target, phase)
        inconsistent |= previous != phase
    representative = min(phase_by_target)
    return {
        "representative": representative,
        "phase_from_representative": phase_by_target[representative],
        "orbit_size": len(phase_by_target),
        "projected_zero": inconsistent,
        "images": images,
    }


def _verify_car_sign_rule(symmetries: list[dict[str, Any]], neel_basis: int) -> dict[str, Any]:
    pair_checks = 0
    for symmetry in symmetries:
        _check_deadline()
        permutation = symmetry["mode_permutation"]
        sites = symmetry["site_permutation"]
        for left in range(128):
            for right in range(left + 1, 128):
                generic = int(permutation[left] > permutation[right])
                left_site, right_site = left // 2, right // 2
                if left_site == right_site:
                    formula = symmetry["shift"]
                else:
                    formula = int(sites[left_site] > sites[right_site])
                if generic != formula:
                    raise SemanticNoGo("car_sign_rule", "CAR quadratic sign decomposition failed")
                pair_checks += 1
    spin_swap_fixture = int("66669999666699996666999966679998", 16)
    negative_stabilizer_fixture = int("000f000f003f003f003f0fcffff9fff6", 16)
    fixtures = (
        0,
        MASK128,
        neel_basis,
        int("0123456789abcdef" * 2, 16),
        int("f0e1d2c3b4a59687" * 2, 16),
        spin_swap_fixture,
        negative_stabilizer_fixture,
    )
    optimized_checks = 0
    for basis in fixtures:
        optimized = _basis_images(basis, symmetries)
        for index, symmetry in enumerate(symmetries):
            if optimized[index] != _generic_mode_action(basis, symmetry["mode_permutation"]):
                raise SemanticNoGo(
                    "car_sign_rule",
                    "optimized CAR action differs from generic wedge action",
                )
            optimized_checks += 1
    spin_target, spin_phase = _basis_images(spin_swap_fixture, symmetries)[1]
    if (
        spin_target != int("66669999666699996666999966663999", 16)
        or spin_phase != -1
    ):
        raise SemanticNoGo("car_sign_rule", "global fermionic spin-swap phase fixture failed")
    negative_info = _canonical_info(negative_stabilizer_fixture, symmetries)
    if negative_info["projected_zero"] is not True:
        raise SemanticNoGo(
            "negative_stabilizer_projection",
            "negative-stabilizer fixture was not projected to zero",
        )
    index_by_permutation = {
        symmetry["mode_permutation"]: index for index, symmetry in enumerate(symmetries)
    }
    cocycle_checks = 0
    for basis in fixtures:
        first_images = _basis_images(basis, symmetries)
        for left_index, left in enumerate(symmetries):
            for right_index, right in enumerate(symmetries):
                intermediate, right_phase = first_images[right_index]
                final, left_phase = _basis_images(intermediate, symmetries)[left_index]
                composed = tuple(
                    left["mode_permutation"][right["mode_permutation"][mode]]
                    for mode in range(128)
                )
                direct = first_images[index_by_permutation[composed]]
                if (final, left_phase * right_phase) != direct:
                    raise SemanticNoGo("car_cocycle", "second-quantized group cocycle failed")
                cocycle_checks += 1
    return {
        "quadratic_pair_checks": pair_checks,
        "optimized_fixture_checks": optimized_checks,
        "cocycle_checks": cocycle_checks,
        "spin_swap_doublon_phase_fixture_pass": True,
        "negative_stabilizer_projection_fixture_pass": True,
        "sign_formula": "(-1)^(inversions_of_site_permutation_on_singly_occupied_sites + spin_swap*number_of_doublons)",
        "pass": True,
    }


def _verify_initial_and_observables(
    symmetries: list[dict[str, Any]], neel_basis: int, contract: Mapping[str, Any]
) -> dict[str, Any]:
    characters: dict[str, int] = {}
    for symmetry, (target, phase) in zip(symmetries, _basis_images(neel_basis, symmetries)):
        if target != neel_basis:
            raise SemanticNoGo(
                "initial_state_character",
                "combined symmetry does not stabilize the Neel basis",
            )
        characters[symmetry["name"]] = phase
    if characters != contract["symmetry_group"]["initial_character"]:
        raise SemanticNoGo("initial_state_character", "Neel character drift")
    magnetization_checks = 0
    doublon_checks = 0
    for symmetry in symmetries:
        for mode, target in enumerate(symmetry["mode_permutation"]):
            site, spin = mode // 2, mode & 1
            target_site, target_spin = target // 2, target & 1
            weight = (1 if (site // 8 + site % 8) % 2 == 0 else -1) * (1 if spin == 0 else -1)
            target_weight = (
                (1 if (target_site // 8 + target_site % 8) % 2 == 0 else -1)
                * (1 if target_spin == 0 else -1)
            )
            if weight != target_weight:
                raise SemanticNoGo(
                    "observable_character",
                    "staggered magnetization is not invariant",
                )
            magnetization_checks += 1
        for site in range(64):
            mapped = {
                symmetry["mode_permutation"][2 * site] // 2,
                symmetry["mode_permutation"][2 * site + 1] // 2,
            }
            if len(mapped) != 1:
                raise SemanticNoGo("observable_character", "double-occupancy site pair split")
            doublon_checks += 1
    return {
        "initial_state_stabilized": True,
        "initial_character": characters,
        "staggered_magnetization_character": 1,
        "double_occupancy_character": 1,
        "magnetization_mode_checks": magnetization_checks,
        "double_occupancy_site_checks": doublon_checks,
        "pass": True,
    }


def _verify_hamiltonian(
    d4: Any,
    backend: Any,
    bonds: Mapping[str, list[tuple[int, int]]],
    symmetries: list[dict[str, Any]],
    neel_basis: int,
) -> dict[str, Any]:
    all_bonds = {tuple(sorted(bond)) for group in bonds.values() for bond in group}
    bond_checks = 0
    onsite_checks = 0
    for symmetry in symmetries:
        permutation = symmetry["mode_permutation"]
        for bond in all_bonds:
            if tuple(sorted((permutation[bond[0]], permutation[bond[1]]))) not in all_bonds:
                raise SemanticNoGo("hamiltonian_equivariance", "hopping bond orbit is not closed")
            bond_checks += 1
        for site in range(64):
            targets = {permutation[2 * site] // 2, permutation[2 * site + 1] // 2}
            if len(targets) != 1:
                raise SemanticNoGo("hamiltonian_equivariance", "onsite term orbit is not closed")
            onsite_checks += 1
    depth_one = d4._sector_action(backend, bonds, {neel_basis: 1}, 2_000_000)
    fixtures = [neel_basis, *sorted(depth_one)[:32]]
    equivariance_checks = 0
    for basis in fixtures:
        _check_deadline()
        action = d4._sector_action(backend, bonds, {basis: 1}, 2_000_000)
        for symmetry in symmetries:
            target_basis, source_phase = _generic_mode_action(basis, symmetry["mode_permutation"])
            transformed: dict[int, int] = {}
            for child, amplitude in action.items():
                target, phase = _generic_mode_action(child, symmetry["mode_permutation"])
                transformed[target] = transformed.get(target, 0) + amplitude * phase
            right = {
                child: amplitude * source_phase
                for child, amplitude in d4._sector_action(
                    backend, bonds, {target_basis: 1}, 2_000_000
                ).items()
            }
            if transformed != right:
                raise SemanticNoGo(
                    "hamiltonian_equivariance",
                    "sector action equivariance fixture failed",
                )
            equivariance_checks += 1
    _, depth_one_quotient = _audit_vector(depth_one, symmetries, materialize_quotient=True)
    assert depth_one_quotient is not None
    metric_sources = sorted({neel_basis, *depth_one_quotient})
    column_cache: dict[int, tuple[dict[int, Fraction], int, int]] = {}

    def get_column(representative: int) -> tuple[dict[int, Fraction], int, int]:
        if representative not in column_cache:
            column_cache[representative] = _reduced_column(
                d4, backend, bonds, representative, symmetries
            )
        return column_cache[representative]

    metric_checks = 0
    for source in metric_sources:
        _check_deadline()
        column, source_orbit_size, _ = get_column(source)
        for target, forward in column.items():
            reverse_column, target_orbit_size, _ = get_column(target)
            reverse = reverse_column.get(source, Fraction(0))
            if target_orbit_size * forward != source_orbit_size * reverse:
                raise SemanticNoGo(
                    "quotient_metric_hermiticity",
                    "per-basis quotient metric Hermiticity failed",
                )
            metric_checks += 1
    return {
        "unique_hopping_bond_count": len(all_bonds),
        "hopping_orbit_checks": bond_checks,
        "onsite_orbit_checks": onsite_checks,
        "action_fixture_basis_count": len(fixtures),
        "action_equivariance_checks": equivariance_checks,
        "metric_hermiticity_source_representatives": len(metric_sources),
        "metric_hermiticity_checks": metric_checks,
        "pass": True,
    }


def _vector_digest_streaming(vector: Mapping[int, int]) -> str:
    digest = hashlib.sha256()
    digest.update(b"[")
    for index, basis in enumerate(sorted(vector)):
        if not (index & 0xFFFF):
            _check_deadline()
        if index:
            digest.update(b",")
        digest.update(json.dumps([hex(basis), str(vector[basis])], separators=(",", ":")).encode("ascii"))
    digest.update(b"]")
    return digest.hexdigest()


def _audit_vector(
    vector: Mapping[int, int],
    symmetries: list[dict[str, Any]],
    materialize_quotient: bool,
) -> tuple[dict[str, Any], dict[int, int] | None]:
    quotient: dict[int, int] | None = {} if materialize_quotient else None
    orbit_histogram: dict[str, int] = {}
    stabilizer_histogram: dict[str, int] = {}
    representative_count = 0
    coverage = 0
    relation_checks = 0
    quotient_digest = hashlib.sha256()
    quotient_digest.update(b"[")
    for basis, amplitude in vector.items():
        if not (relation_checks & 0x7FFFF):
            _check_deadline()
        info = _canonical_info(basis, symmetries)
        if info["projected_zero"]:
            raise SemanticNoGo(
                "full_orbit_relations",
                "nonzero Krylov state has a negative stabilizer character",
            )
        for target, phase in info["images"]:
            if vector.get(target) != amplitude * phase:
                raise SemanticNoGo(
                    "full_orbit_relations",
                    "full-vector orbit amplitude relation failed",
                )
            relation_checks += 1
        if basis != info["representative"]:
            continue
        orbit_size = info["orbit_size"]
        if 8 % orbit_size:
            raise SemanticNoGo(
                "full_orbit_relations", "orbit size does not divide group order"
            )
        representative_count += 1
        coverage += orbit_size
        orbit_histogram[str(orbit_size)] = orbit_histogram.get(str(orbit_size), 0) + 1
        stabilizer = 8 // orbit_size
        stabilizer_histogram[str(stabilizer)] = stabilizer_histogram.get(str(stabilizer), 0) + 1
        if quotient is not None:
            quotient[basis] = amplitude
        if representative_count > 1:
            quotient_digest.update(b",")
        quotient_digest.update(
            json.dumps(
                [hex(basis), str(amplitude), orbit_size], separators=(",", ":")
            ).encode("ascii")
        )
    quotient_digest.update(b"]")
    if coverage != len(vector):
        raise SemanticNoGo(
            "full_orbit_relations",
            "orbit representatives do not exactly cover the full vector",
        )
    return (
        {
            "full_state_count": len(vector),
            "orbit_representative_count": representative_count,
            "compression_ratio": f"{len(vector)}/{representative_count}",
            "orbit_size_histogram": dict(sorted(orbit_histogram.items(), key=lambda item: int(item[0]))),
            "stabilizer_size_histogram": dict(
                sorted(stabilizer_histogram.items(), key=lambda item: int(item[0]))
            ),
            "coverage_sum": coverage,
            "amplitude_relation_checks": relation_checks,
            "projected_zero_nonzero_states": 0,
            "deterministic_insertion_order_quotient_sha256": quotient_digest.hexdigest(),
        },
        quotient,
    )


def _reduced_column(
    d4: Any,
    backend: Any,
    bonds: Mapping[str, list[tuple[int, int]]],
    representative: int,
    symmetries: list[dict[str, Any]],
) -> tuple[dict[int, Fraction], int, int]:
    source_info = _canonical_info(representative, symmetries)
    if source_info["representative"] != representative or source_info["projected_zero"]:
        raise SemanticNoGo(
            "quotient_transition_equivalence",
            "quotient key is not an admissible representative",
        )
    source_orbit_size = source_info["orbit_size"]
    output: dict[int, Fraction] = {}
    projected_zero_outputs = 0
    action = d4._sector_action(backend, bonds, {representative: 1}, 2_000_000)
    for child, coefficient in action.items():
        target_info = _canonical_info(child, symmetries)
        if target_info["projected_zero"]:
            projected_zero_outputs += 1
            continue
        target = target_info["representative"]
        contribution = Fraction(
            coefficient
            * target_info["phase_from_representative"]
            * source_orbit_size,
            target_info["orbit_size"],
        )
        output[target] = output.get(target, Fraction(0)) + contribution
    return output, source_orbit_size, projected_zero_outputs


def _quotient_step(
    d4: Any,
    backend: Any,
    bonds: Mapping[str, list[tuple[int, int]]],
    quotient: Mapping[int, int],
    symmetries: list[dict[str, Any]],
) -> tuple[dict[int, int], dict[str, int]]:
    output: dict[int, Fraction] = {}
    nonzero_action_outputs = 0
    projected_zero_outputs = 0
    for representative_index, (representative, amplitude) in enumerate(quotient.items()):
        if not (representative_index & 0x3FF):
            _check_deadline()
        column, _, projected_zero = _reduced_column(
            d4, backend, bonds, representative, symmetries
        )
        nonzero_action_outputs += len(column)
        projected_zero_outputs += projected_zero
        for target, coefficient in column.items():
            output[target] = output.get(target, Fraction(0)) + amplitude * coefficient
    cleaned: dict[int, int] = {}
    for basis, amplitude in output.items():
        if not amplitude:
            continue
        if amplitude.denominator != 1:
            raise SemanticNoGo(
                "quotient_transition_equivalence",
                "quotient transition produced a nonintegral full-basis amplitude",
            )
        cleaned[basis] = amplitude.numerator
    return cleaned, {
        "source_representative_count": len(quotient),
        "candidate_action_upper_bound": len(quotient) * 225,
        "nonzero_reduced_column_outputs": nonzero_action_outputs,
        "projected_zero_action_outputs": projected_zero_outputs,
    }


def decide(
    semantic_gates: Mapping[str, bool],
    metrics: Mapping[str, int],
    limits: Mapping[str, int],
) -> dict[str, Any]:
    semantic_pass = bool(semantic_gates) and all(value is True for value in semantic_gates.values())
    resource_gates = {
        "orbit_representatives_within_cap": metrics["orbit_representatives"]
        <= limits["max_orbit_representatives"],
        "next_action_within_cap": metrics["next_action_upper_bound"]
        <= limits["max_next_action_candidates"],
        "audit_transforms_within_cap": metrics["audit_group_actions"]
        <= limits["max_audit_group_actions"],
    }
    if not semantic_pass:
        status = SEMANTIC_NO_GO
    elif not all(resource_gates.values()):
        status = RESOURCE_NO_GO
    else:
        status = PASS_STATUS
    return {
        "status": status,
        "semantic_gates_pass": semantic_pass,
        "resource_gates": resource_gates,
        "d6_design_eligible": status == PASS_STATUS,
        "d6_execution_authorized": False,
    }


def recompute(contract: Mapping[str, Any], protocol_commit: str) -> dict[str, Any]:
    global _ACTIVE_DEADLINE
    _validate_contract(contract)
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != contract.get("checker_self_sha256"):
        raise VerificationError("D5 checker self pin drift")
    protocol = _verify_protocol_commit(contract, protocol_commit)
    resource_envelope = _verify_resource_envelope(contract)
    _ACTIVE_DEADLINE = time.monotonic() + contract["resource_limits"]["maximum_seconds"]
    d4, d4_contract, _ = _verify_parent_sources(contract)
    d3 = d4._load_d3(d4_contract)
    d3_contract = _load_json(HERE / "fh_l8_degree6_streaming_d3_contract.json")
    d2 = d3._load_d2(d3_contract)
    d2_contract = _load_json(HERE / "fh_l8_two_step_scalar_defect_d2_contract.json")
    upstream = d2._load_upstream(d2_contract)
    backend = upstream._load_backend()
    bonds = {name: backend._hopping_bonds(8, name) for name in ("H1", "H2", "H3", "H4")}
    neel_basis = upstream._neel_basis(8)
    if hex(neel_basis) != contract["workload"]["neel_basis_hex"]:
        raise VerificationError("Neel basis drift")
    symmetries, group_record = _build_symmetries(contract)
    car_record = _verify_car_sign_rule(symmetries, neel_basis)
    observable_record = _verify_initial_and_observables(symmetries, neel_basis, contract)
    hamiltonian_record = _verify_hamiltonian(d4, backend, bonds, symmetries, neel_basis)

    expected_prefix = d4_contract["sector_krylov_candidate"]
    vector: dict[int, int] = {neel_basis: 1}
    depth_records: list[dict[str, Any]] = []
    transition_records: list[dict[str, Any]] = []
    predicted_quotient: dict[int, int] | None = None
    final_quotient: dict[int, int] | None = None
    for depth in range(4):
        if len(vector) > contract["resource_limits"]["max_materialized_states"]:
            raise ResourceNoGo(
                "full_krylov_state_cap", "full Krylov state cap exceeded"
            )
        vector_digest = _vector_digest_streaming(vector)
        if len(vector) != expected_prefix["reachable_state_counts"][depth]:
            raise VerificationError("D4 Krylov count drift")
        if vector_digest != expected_prefix["state_digests"][depth]:
            raise VerificationError("D4 Krylov digest drift")
        audit, quotient = _audit_vector(vector, symmetries, materialize_quotient=True)
        assert quotient is not None
        if predicted_quotient is not None:
            if predicted_quotient != quotient:
                raise SemanticNoGo(
                    "quotient_transition_equivalence",
                    "full and quotient Krylov transitions differ",
                )
            transition_records[-1]["matches_next_full_quotient"] = True
        depth_records.append({"depth": depth, "full_vector_sha256": vector_digest, **audit})
        if depth < 3:
            predicted_quotient, transition = _quotient_step(
                d4, backend, bonds, quotient, symmetries
            )
            transition_records.append(
                {
                    "source_depth": depth,
                    "target_depth": depth + 1,
                    **transition,
                    "matches_next_full_quotient": False,
                }
            )
            vector = d4._sector_action(
                backend,
                bonds,
                vector,
                contract["resource_limits"]["max_materialized_states"],
            )
        else:
            final_quotient = quotient

    assert final_quotient is not None
    semantic_gates = {
        "group_closure": group_record["closure_pass"],
        "car_sign_rule": car_record["pass"],
        "hamiltonian_equivariance": hamiltonian_record["pass"],
        "initial_and_observable_characters": observable_record["pass"],
        "full_orbit_relations": all(
            item["amplitude_relation_checks"] == 8 * item["full_state_count"]
            and item["coverage_sum"] == item["full_state_count"]
            and item["projected_zero_nonzero_states"] == 0
            for item in depth_records
        ),
        "quotient_transition_equivalence_depths_0_1_2": all(
            item["matches_next_full_quotient"] is True for item in transition_records
        ),
        "fourth_action_not_executed": True,
    }
    final_representatives = depth_records[-1]["orbit_representative_count"]
    metrics = {
        "orbit_representatives": final_representatives,
        "next_action_upper_bound": final_representatives * 225,
        "audit_group_actions": sum(item["amplitude_relation_checks"] for item in depth_records),
    }
    decision = decide(semantic_gates, metrics, contract["resource_limits"])
    evidence = {
        "contract_id": CONTRACT_ID,
        "status": decision["status"],
        "verified": True,
        "protocol_freeze": protocol,
        "parent": {
            "contract_id": d4_contract["contract_id"],
            "integration_commit": contract["parent"]["integration_commit"],
            "integration_tree": contract["parent"]["integration_tree"],
            "source_pins_pass": True,
        },
        "resource_envelope": resource_envelope,
        "semantic_proof": {
            "group": group_record,
            "car": car_record,
            "initial_and_observables": observable_record,
            "hamiltonian": hamiltonian_record,
        },
        "krylov_prefix": {
            "depth_records": depth_records,
            "quotient_transition_records": transition_records,
        },
        "resource_projection": {
            **metrics,
            "candidate_actions_per_representative": 225,
            "next_action_orbit_transform_upper_bound": metrics["next_action_upper_bound"] * 8,
            "limits": dict(contract["resource_limits"]),
        },
        "decision": decision,
        "semantic_gates": semantic_gates,
        "authority": {
            "d6_design_eligible": decision["d6_design_eligible"],
            "d6_execution_authorized": False,
            "fourth_hamiltonian_action_executed": False,
            "degree6_remainder_bounded": False,
            "two_step_cumulative_error_bounded": False,
            "full_R100_error_bounded": False,
            "physical_reference_qualified": False,
            "ready_gate_eligible": False,
        },
        "limitations": list(contract["forbidden_claims"]),
    }
    return evidence


def _failure_evidence(
    contract: Mapping[str, Any], protocol_commit: str, failure: SemanticNoGo | ResourceNoGo
) -> dict[str, Any]:
    _validate_contract(contract)
    protocol = _verify_protocol_commit(contract, protocol_commit)
    resource_envelope = _verify_resource_envelope(contract)
    _, d4_contract, _ = _verify_parent_sources(contract)
    semantic = isinstance(failure, SemanticNoGo)
    status = SEMANTIC_NO_GO if semantic else RESOURCE_NO_GO
    return {
        "contract_id": CONTRACT_ID,
        "status": status,
        "verified": True,
        "protocol_freeze": protocol,
        "parent": {
            "contract_id": d4_contract["contract_id"],
            "integration_commit": contract["parent"]["integration_commit"],
            "integration_tree": contract["parent"]["integration_tree"],
            "source_pins_pass": True,
        },
        "resource_envelope": resource_envelope,
        "failure": {
            "class": "SEMANTIC_GATE" if semantic else "RESOURCE_GATE",
            "gate": failure.gate,
            "detail": failure.detail,
        },
        "decision": {
            "status": status,
            "semantic_gates_pass": False if semantic else None,
            "resource_gates_pass": None if semantic else False,
            "d6_design_eligible": False,
            "d6_execution_authorized": False,
        },
        "authority": {
            "d6_design_eligible": False,
            "d6_execution_authorized": False,
            "fourth_hamiltonian_action_executed": False,
            "degree6_remainder_bounded": False,
            "two_step_cumulative_error_bounded": False,
            "full_R100_error_bounded": False,
            "physical_reference_qualified": False,
            "ready_gate_eligible": False,
        },
        "limitations": list(contract["forbidden_claims"]),
    }


def evaluate(contract: Mapping[str, Any], protocol_commit: str) -> dict[str, Any]:
    global _ACTIVE_DEADLINE
    try:
        try:
            return recompute(contract, protocol_commit)
        except (SemanticNoGo, ResourceNoGo) as failure:
            return _failure_evidence(contract, protocol_commit, failure)
    finally:
        _ACTIVE_DEADLINE = None


def verify(contract: Mapping[str, Any], result: Mapping[str, Any], protocol_commit: str) -> dict[str, Any]:
    evidence = evaluate(contract, protocol_commit)
    if result != evidence:
        raise VerificationError("result does not equal recomputed D5 evidence")
    return evidence


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol-commit", required=True)
    parser.add_argument("--evidence", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        contract = _load_json(HERE / "fh_l8_symmetry_orbit_quotient_d5_contract.json")
        if args.evidence:
            evidence = evaluate(contract, args.protocol_commit)
        else:
            result = _load_json(HERE / "fh_l8_symmetry_orbit_quotient_d5_result.json")
            evidence = verify(contract, result, args.protocol_commit)
    except (
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        VerificationError,
        ValueError,
        TypeError,
        KeyError,
        AssertionError,
    ) as exc:
        print(json.dumps({"status": "VERIFICATION_FAILED", "verified": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
