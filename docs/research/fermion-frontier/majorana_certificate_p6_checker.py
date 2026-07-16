#!/usr/bin/env python3
"""Independent checker for the Majorana P6 adaptive-drop campaign.

The sole formal candidate starts from O0, freshly executes the certified P3
step-one path with the strict 2^-34 threshold, and executes the frozen E768
full-domain adaptive second step in the same process.  Exactly two isolated
processes are required and their canonical stdout bytes must be identical.

The Julia runner is result blind.  Only after both raw processes finish does
this checker independently reconstruct every binary64 operation and every
adaptive boundary, check P3 fieldwise conformance, inherit P3 E1 once, and
apply the frozen strict local and cumulative allocation tests.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from fractions import Fraction
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any, Iterator, Mapping, MutableMapping, Sequence
import uuid


BASE = Path(__file__).resolve().parent
FIXTURE_NAME = "majorana_certificate_p6_fixture.json"
POLICY_NAME = "majorana_certificate_p6_policy.json"
PRECOMMIT_CONTRACT_NAME = "majorana_certificate_p6_precommit_contract.json"
RESULT_CONTRACT_NAME = "majorana_certificate_p6_contract.json"
CERTIFICATE_NAME = "majorana_certificate_p6_certificate.json"
RESULT_TEST_NAME = "test_majorana_certificate_p6_result.py"
PRECOMMIT_TEST_NAME = "test_majorana_certificate_p6.py"
CHECKER_NAME = "majorana_certificate_p6_checker.py"
RUNNER_RELATIVE_PATH = "majorana_certificate_p6/majorana_p6_runner.jl"
RESULT_ARTIFACTS = (RESULT_CONTRACT_NAME, CERTIFICATE_NAME, RESULT_TEST_NAME)

P5_CHECKER_NAME = "majorana_certificate_p5_checker.py"
P5_FIXTURE_NAME = "majorana_certificate_p5_fixture.json"
P5_POLICY_NAME = "majorana_certificate_p5_policy.json"
P5_RESULT_CONTRACT_NAME = "majorana_certificate_p5_contract.json"
P5_CERTIFICATE_NAME = "majorana_certificate_p5_certificate.json"
P5_RESULT_TEST_NAME = "test_majorana_certificate_p5_result.py"
P5_RUNNER_RELATIVE_PATH = "majorana_certificate_p5/majorana_p5_runner.jl"

P4_CHECKER_NAME = "majorana_certificate_p4_checker.py"
P4_FIXTURE_NAME = "majorana_certificate_p4_fixture.json"
P4_POLICY_NAME = "majorana_certificate_p4_policy.json"
P4_PRECOMMIT_CONTRACT_NAME = "majorana_certificate_p4_precommit_contract.json"
P4_RESULT_CONTRACT_NAME = "majorana_certificate_p4_contract.json"
P4_CERTIFICATE_NAME = "majorana_certificate_p4_certificate.json"
P4_RESULT_TEST_NAME = "test_majorana_certificate_p4_result.py"
P3_FIXTURE_NAME = "majorana_certificate_p3_fixture.json"
P3_RESULT_CONTRACT_NAME = "majorana_certificate_p3_contract.json"
P3_CERTIFICATE_NAME = "majorana_certificate_p3_certificate.json"
P2_FIXTURE_NAME = "majorana_certificate_p2_fixture.json"
RUNTIME_LOCK_NAME = "majorana_certificate_p0_runtime_lock.json"
D0_POLICY_NAME = "majorana_certificate_p6_design_probe_policy.json"
D0_FIXTURE_NAME = "majorana_certificate_p6_design_probe_fixture.json"
D0_REPORT_NAME = "majorana_certificate_p6_design_probe_report.json"
D0_CHECKER_NAME = "majorana_certificate_p6_design_probe.py"
D0_PRECOMMIT_TEST_NAME = "test_majorana_certificate_p6_design_probe.py"
D0_RESULT_TEST_NAME = "test_majorana_certificate_p6_design_probe_result.py"
D0_RUNNER_RELATIVE_PATH = (
    "majorana_certificate_p6_design_probe/majorana_p6_adaptive_drop_resource_probe.jl"
)

REQUIRED_PARENT_COMMIT = "f62005b435a0c033d42aae0d05c05e234faab059"
P5_RESULT_COMMIT = "39100195cfd04bb4de086f127e8a75da0a7548ce"
P4_RESULT_COMMIT = "b0028fbd9ac079a64406bc2808ef7943045887a3"
P3_RESULT_COMMIT = "d5b63abe941ff0a723dd7c15a61b9ab8298286ab"

FIXTURE_ID = "MAJORANA-P6-L8-E768-MAX-LAZY37-S0-V1"
FIXTURE_CANONICAL_SHA256 = (
    "10bb6f8877abcf4fe6453e65825b288f6236b8aa3c9d799ce4a5c7c81ae96760"
)
POLICY_CANONICAL_SHA256 = (
    "ec28a33338303b9892c1e1f696d3ec312eeca3c1e4948dd5ea24cab276036ddc"
)
RAW_WITNESS_TYPE = "majorana_p6_L8_E768_MAX_LAZY37_execution_raw_v1"
COMPOSED_WITNESS_TYPE = (
    "majorana_p6_L8_E768_MAX_LAZY37_authoritative_witness_v1"
)
PACKAGE_TYPE = "majorana_p6_formal_fresh_E768_MAX_LAZY37_replay_package_v1"
PRECOMMIT_CONTRACT_TYPE = (
    "majorana_p6_result_unpinned_E768_MAX_LAZY37_input_and_isolation_contract_v1"
)
RESULT_CONTRACT_TYPE = "majorana_p6_formal_E768_MAX_LAZY37_result_contract_v1"
CERTIFICATE_TYPE = "majorana_p6_E768_MAX_LAZY37_bound_subcertificate_v1"

ACCEPT_STATUS = (
    "VERIFIED_MAJORANA_P6_L8_E768_MAX_LAZY37_LOCAL_AND_CUMULATIVE_"
    "ERROR_BOUNDS_WITHIN_ALLOCATIONS_SUBCERTIFICATE"
)
REJECT_LOCAL_STATUS = (
    "VERIFIED_MAJORANA_P6_L8_E768_MAX_LAZY37_LOCAL_ALLOCATION_"
    "EXCEEDED_BOUNDED_NEGATIVE_SUBCERTIFICATE"
)
REJECT_BOTH_STATUS = (
    "VERIFIED_MAJORANA_P6_L8_E768_MAX_LAZY37_LOCAL_AND_CUMULATIVE_"
    "ALLOCATIONS_EXCEEDED_BOUNDED_NEGATIVE_SUBCERTIFICATE"
)
CAP_STATUS = "VERIFIED_MAJORANA_P6_E768_POLICY_CAP_EXCEEDED_SUBCERTIFICATE"
FAILED_CONFORMANCE_STATUS = "FAILED_MAJORANA_P6_STEP1_P3_POST_REPLAY_CONFORMANCE"
INDETERMINATE_STATUS = "INDETERMINATE_MAJORANA_P6_REPLAY"
INVALID_STATUS = "INVALID_MAJORANA_P6_REPLAY"
MAXIMUM_STATUS = ACCEPT_STATUS

STEP2_ALLOCATION = Fraction(1, 400000)
CUMULATIVE_ALLOCATION = Fraction(1, 200000)
STEP1_THRESHOLD_BITS = 0x3DD0000000000000
CANDIDATE_ID = "E768-MAX-LAZY37-V1"
CANDIDATE_ORDER = (CANDIDATE_ID,)
LAZY_ANCHOR_BITS = 0x3DA0000000000000
BOUNDARY_COUNT = 768
MAXIMUM_STRICT_LOCAL_TICKS = ((1 << 128) - 1) // 400000


def _load_helper(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P5 = _load_helper("majorana_p6_p5_helper", BASE / P5_CHECKER_NAME)
P4 = P5.P4
P3 = P5.P3
P2 = P5.P2
P0 = P5.P0
SchemaError = P5.SchemaError
VerificationError = P5.VerificationError
IndeterminateReplay = P5.IndeterminateReplay
canonical_bytes = P5.canonical_bytes
canonical_sha256 = P5.canonical_sha256
file_sha256 = P5.file_sha256
require_exact_keys = P5.require_exact_keys
require_sha256 = P5.require_sha256
GRID = P5.GRID
GRID_BITS = P5.GRID_BITS
SIGN_MASK = P5.SIGN_MASK
REPLAY_ENVIRONMENT_TARGETS = P5.REPLAY_ENVIRONMENT_TARGETS


def _derive_raw_witness_schema_max_bytes(fixture: Mapping[str, Any]) -> int:
    """Mechanically derive the result-blind raw witness byte upper bound."""

    budget = fixture.get("scientific_output_schema_budget")
    if not isinstance(budget, dict):
        raise SchemaError("P6 fixture lacks scientific output schema budget")
    products = (
        ("maximum_transition_record_count", "maximum_transition_record_bytes"),
        ("maximum_boundary_record_count", "maximum_boundary_record_bytes"),
        ("maximum_stage_record_count", "maximum_stage_record_bytes"),
    )
    derived = _positive_int(
        budget.get("fixed_envelope_max_bytes"), "P6 fixed witness envelope"
    )
    for count_key, width_key in products:
        derived += _positive_int(budget.get(count_key), count_key) * _positive_int(
            budget.get(width_key), width_key
        )
    if derived != budget.get("raw_witness_schema_max_bytes"):
        raise VerificationError("P6 raw witness schema byte derivation drift")
    return derived


def _smallest_power_of_two_at_least(value: int) -> int:
    _positive_int(value, "power-of-two input")
    return 1 << (value - 1).bit_length()


def _derive_persisted_result_byte_cap(fixture: Mapping[str, Any]) -> int:
    budget = fixture.get("scientific_output_schema_budget")
    if not isinstance(budget, dict):
        raise SchemaError("P6 fixture lacks scientific output schema budget")
    raw_bound = _derive_raw_witness_schema_max_bytes(fixture)
    stdout_cap = _smallest_power_of_two_at_least(raw_bound)
    if stdout_cap != budget.get("maximum_stdout_bytes"):
        raise VerificationError("P6 stdout cap is not schema-derived")
    process_count = _positive_int(budget.get("fresh_process_count"), "fresh process count")
    persisted = process_count * stdout_cap
    if persisted != budget.get("maximum_persisted_result_bytes"):
        raise VerificationError("P6 persisted result cap derivation drift")
    return persisted


def _persisted_result_byte_cap(base: Path = BASE) -> int:
    return _derive_persisted_result_byte_cap(load_json(Path(base) / FIXTURE_NAME))


def _strict_persisted_json_loads(
    data: bytes, *, source: str, maximum_bytes: int,
) -> Any:
    """Strict bounded parser shared by P6 stdout and persisted containers."""

    if len(data) > maximum_bytes:
        raise SchemaError("P6 JSON exceeds its derived byte cap")

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise SchemaError(f"duplicate JSON key: {key}")
            output[key] = value
        return output

    def reject_float(_: str) -> Any:
        raise SchemaError("JSON floating-point numbers are forbidden")

    def parse_integer(text: str) -> int:
        if text == "-0":
            raise SchemaError("JSON negative zero is forbidden")
        value = int(text)
        if value.bit_length() > 2048:
            raise SchemaError("JSON integer exceeds the P6 bit cap")
        return value

    try:
        return json.loads(
            data.decode("utf-8"), object_pairs_hook=object_pairs,
            parse_float=reject_float, parse_int=parse_integer,
            parse_constant=reject_float,
        )
    except (SchemaError, VerificationError):
        raise
    except UnicodeDecodeError as error:
        raise SchemaError(f"{source} is not UTF-8") from error
    except json.JSONDecodeError as error:
        raise SchemaError(f"invalid {source}") from error
    except Exception as error:
        raise SchemaError(f"invalid {source}") from error


def _load_persisted_json(path: Path, base: Path = BASE) -> Any:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise SchemaError(f"JSON input is not a regular file: {path}")
    return _strict_persisted_json_loads(
        path.read_bytes(), source=str(path),
        maximum_bytes=_persisted_result_byte_cap(base),
    )


RUNNER_STAGED_PATHS = (
    "majorana_certificate_p0/Manifest.toml",
    "majorana_certificate_p0/Project.toml",
    "majorana_certificate_p2/majorana_p2_runner.jl",
    P2_FIXTURE_NAME,
    "majorana_certificate_p3/majorana_p3_runner.jl",
    P3_FIXTURE_NAME,
    "majorana_certificate_p4/majorana_p4_runner.jl",
    P4_FIXTURE_NAME,
    P5_FIXTURE_NAME,
    RUNNER_RELATIVE_PATH,
    FIXTURE_NAME,
)

RUNNER_FORBIDDEN_PATHS = (
    "majorana_certificate_p2_contract.json",
    "majorana_certificate_p2_certificate.json",
    "test_majorana_certificate_p2_result.py",
    P3_RESULT_CONTRACT_NAME,
    P3_CERTIFICATE_NAME,
    "test_majorana_certificate_p3_result.py",
    P4_RESULT_CONTRACT_NAME,
    P4_CERTIFICATE_NAME,
    P4_RESULT_TEST_NAME,
    P5_RESULT_CONTRACT_NAME,
    P5_CERTIFICATE_NAME,
    P5_RESULT_TEST_NAME,
    P5_RUNNER_RELATIVE_PATH,
    D0_FIXTURE_NAME,
    D0_POLICY_NAME,
    D0_REPORT_NAME,
    D0_CHECKER_NAME,
    D0_PRECOMMIT_TEST_NAME,
    D0_RESULT_TEST_NAME,
    D0_RUNNER_RELATIVE_PATH,
    RESULT_CONTRACT_NAME,
    CERTIFICATE_NAME,
    RESULT_TEST_NAME,
)

# This is the outer checker's custody closure, not the runner stage.  It may
# contain the result-bearing P3/P4 and non-authoritative D0 artifacts, but those
# rows are opened only after both raw processes finish in ``fresh_replay``.
PRECOMMIT_SOURCE_PATHS = tuple(sorted(set(P5.PRECOMMIT_SOURCE_PATHS) | {
    P4_PRECOMMIT_CONTRACT_NAME,
    P4_RESULT_CONTRACT_NAME,
    P4_CERTIFICATE_NAME,
    P4_RESULT_TEST_NAME,
    P5_RESULT_CONTRACT_NAME,
    P5_CERTIFICATE_NAME,
    P5_RESULT_TEST_NAME,
    D0_FIXTURE_NAME,
    D0_POLICY_NAME,
    D0_REPORT_NAME,
    D0_CHECKER_NAME,
    D0_PRECOMMIT_TEST_NAME,
    D0_RESULT_TEST_NAME,
    D0_RUNNER_RELATIVE_PATH,
    RUNNER_RELATIVE_PATH,
    CHECKER_NAME,
    FIXTURE_NAME,
    POLICY_NAME,
    PRECOMMIT_TEST_NAME,
}))

# The formal precommit is a direct child of the D0 design result and may add
# only these six P6 S0 files.  This closes the Git tree against renamed raw
# transcripts, witnesses, result artifacts, or unrelated side-channel files.
PRECOMMIT_CHANGED_PATHS = tuple(sorted((
    RUNNER_RELATIVE_PATH,
    CHECKER_NAME,
    FIXTURE_NAME,
    POLICY_NAME,
    PRECOMMIT_TEST_NAME,
    PRECOMMIT_CONTRACT_NAME,
)))

RAW_SCOPE = {
    "fixed_L8_P3_step1_then_one_candidate_step2_only": True,
    "step1_fixed_2^-34_path_is_unchanged": True,
    "adaptive_step2_local_defect_and_Neel_enclosure": "ASSESSED",
    "candidate_qualification_and_cumulative_allocation": "OUTER_CHECKER_ONLY",
    "global_two_step_or_coefficientwise_interval_state": "NOT_CLAIMED_BY_RUNNER",
    "full_domain_prefix_escrow_drop_set": "ASSESSED",
    "remaining_98_mapped_steps_or_full_R100": "NOT_ASSESSED",
    "product_formula_to_exact_Hubbard_error_or_exact_time_evolution": "NOT_ASSESSED",
    "double_occupancy": "NOT_ASSESSED",
    "arbitrary_initial_state_or_lattice_size": "NOT_CLAIMED",
    "P3_P4_or_P5_result_available_to_runner": False,
    "D0_report_is_not_a_runner_input": True,
    "scientific_authority_claimed_by_raw_witness": False,
    "physical_reference_qualified": False,
    "ready_gate_eligible": False,
}

_STEP_CAP_KEYS = P4._STEP_CAP_KEYS
_CUMULATIVE_CAP_KEYS = P4._CUMULATIVE_CAP_KEYS
_P4_GLOBAL_LOCK = threading.RLock()


def load_json(path: Path) -> Any:
    return P3.load_json(path)


def _format_q(value: Fraction) -> str:
    return P3._format_q(value)


def _positive_int(value: Any, context: str) -> int:
    if type(value) is not int or value <= 0:
        raise SchemaError(f"{context} must be a positive integer")
    return value


@contextmanager
def _p4_module_base(base: Path) -> Iterator[None]:
    """Make every imported legacy module/default honor P5's custom base.

    P4 v2 contains one direct module-level ``BASE`` lookup and several older
    helpers have ``base=BASE`` defaults captured at definition time.  Merely
    assigning ``P4.BASE`` therefore does not repair a copied-closure audit.
    Under one lock we redirect both module globals and those captured Path
    defaults, then restore every object even when verification fails.
    """

    base = Path(base).resolve()
    with _P4_GLOBAL_LOCK:
        modules = (P4, P3, P2, P0)
        previous_bases: list[tuple[Any, Any]] = []
        previous_defaults: list[tuple[Any, Any, Any]] = []
        for module in modules:
            previous_base = getattr(module, "BASE", None)
            previous_bases.append((module, previous_base))
            if previous_base is not None:
                module.BASE = base
            for candidate in vars(module).values():
                if not callable(candidate):
                    continue
                defaults = getattr(candidate, "__defaults__", None)
                kwdefaults = getattr(candidate, "__kwdefaults__", None)
                changed_defaults = defaults
                changed_kwdefaults = kwdefaults
                if defaults and previous_base is not None:
                    changed_defaults = tuple(
                        base if isinstance(item, Path) and item == previous_base else item
                        for item in defaults
                    )
                if kwdefaults and previous_base is not None:
                    changed_kwdefaults = {
                        key: (
                            base if isinstance(item, Path) and item == previous_base
                            else item
                        )
                        for key, item in kwdefaults.items()
                    }
                if changed_defaults != defaults or changed_kwdefaults != kwdefaults:
                    previous_defaults.append((candidate, defaults, kwdefaults))
                    candidate.__defaults__ = changed_defaults
                    candidate.__kwdefaults__ = changed_kwdefaults
        try:
            yield
        finally:
            for candidate, defaults, kwdefaults in reversed(previous_defaults):
                candidate.__defaults__ = defaults
                candidate.__kwdefaults__ = kwdefaults
            for module, previous_base in reversed(previous_bases):
                if previous_base is not None:
                    module.BASE = previous_base


_EXPECTED_STEP2_CAPS = {
    "maximum_current_terms_before_constituent": 1048576,
    "maximum_premerge_terms": 1048576,
    "maximum_boundary_retained_terms": 1048576,
    "maximum_cap_scan_term_visits": 536870912,
    "maximum_propagation_term_visits": 536870912,
    "maximum_truncation_term_visits": 268435456,
    "maximum_final_evaluation_term_visits": 1048576,
    "maximum_total_charged_term_visits": 1073741824,
    "maximum_anticommuting_events": 16777216,
    "maximum_product_defect_events": 33554432,
    "maximum_merge_defect_events": 4194304,
    "maximum_drop_defect_events": 16777216,
    "maximum_accuracy_charged_events": 67108864,
    "maximum_total_P2_plus_accuracy_charged_events": 1073741824,
    "maximum_composites": 512,
    "maximum_constituents": 1152,
    "maximum_truncation_boundaries": 768,
}

_EXPECTED_SELECTION_CAPS = {
    "maximum_peak_ranking_buffer_terms": 1048576,
    "maximum_ranking_scan_term_visits": 268435456,
    "maximum_selected_membership_insertions": 16777216,
    "maximum_sort_input_items": 67108864,
    "maximum_tick_evaluations": 67108864,
    "maximum_total_selection_work_units": 536870912,
}


def _resource_cap_sections(
    fixture: Mapping[str, Any], base: Path = BASE,
) -> tuple[Mapping[str, int], Mapping[str, int], Mapping[str, int], int]:
    """Normalize the certified P3 prefix and common D0-derived step-two caps."""

    with _p4_module_base(Path(base)):
        p4_fixture = P4.validate_fixture(load_json(Path(base) / P4_FIXTURE_NAME))
        p4_step1, _p4_step2, _p4_cumulative, _p4_trig = P4._resource_cap_sections(
            p4_fixture, Path(base),
        )
    root = fixture["deterministic_resource_caps"]
    step2 = {
        "maximum_current_terms_before_constituent": root[
            "maximum_step2_current_terms_before_constituent"
        ],
        "maximum_premerge_terms": root["maximum_step2_premerge_terms"],
        "maximum_boundary_retained_terms": root[
            "maximum_step2_boundary_retained_terms"
        ],
        "maximum_cap_scan_term_visits": root[
            "maximum_step2_cap_scan_term_visits"
        ],
        "maximum_propagation_term_visits": root[
            "maximum_step2_propagation_term_visits"
        ],
        "maximum_truncation_term_visits": root[
            "maximum_step2_truncation_term_visits"
        ],
        "maximum_final_evaluation_term_visits": root[
            "maximum_step2_final_retained_terms"
        ],
        "maximum_total_charged_term_visits": root[
            "maximum_step2_total_P2_charged_term_visits"
        ],
        "maximum_anticommuting_events": root[
            "maximum_step2_anticommuting_events"
        ],
        "maximum_product_defect_events": root[
            "maximum_step2_product_defect_events"
        ],
        "maximum_merge_defect_events": root[
            "maximum_step2_merge_defect_events"
        ],
        "maximum_drop_defect_events": root[
            "maximum_step2_drop_defect_events"
        ],
        "maximum_accuracy_charged_events": root[
            "maximum_step2_accuracy_charged_events"
        ],
        "maximum_total_P2_plus_accuracy_charged_events": root[
            "maximum_step2_total_P2_plus_accuracy_charged_events"
        ],
        "maximum_composites": 512,
        "maximum_constituents": 1152,
        "maximum_truncation_boundaries": 768,
    }
    P4._validate_cap_map(p4_step1, _STEP_CAP_KEYS, "P6 normalized step1 caps")
    P4._validate_cap_map(step2, _STEP_CAP_KEYS, "P6 normalized step2 caps")
    if step2 != _EXPECTED_STEP2_CAPS:
        raise VerificationError("P6 formal step2 caps differ from the frozen D0 derivation")
    instantaneous = {
        "maximum_current_terms_before_constituent",
        "maximum_premerge_terms",
        "maximum_boundary_retained_terms",
    }
    cumulative = {
        key: max(p4_step1[key], step2[key]) if key in instantaneous
        else p4_step1[key] + step2[key]
        for key in _CUMULATIVE_CAP_KEYS
    }
    P4._validate_cap_map(cumulative, _CUMULATIVE_CAP_KEYS, "P6 cumulative caps")
    if (
        cumulative["maximum_accuracy_charged_events"] != 69206016
        or cumulative["maximum_total_charged_term_visits"] != 1140850688
        or cumulative["maximum_total_P2_plus_accuracy_charged_events"] != 1140850688
    ):
        raise VerificationError("P6 cumulative cap derivation drift")
    maximum_trig = _positive_int(
        root["maximum_trig_table_entries"], "P6 maximum_trig_table_entries",
    )
    if maximum_trig != len(P3.ALLOWED_ANGLES):
        raise VerificationError("P6 trigonometric table cap mismatch")
    return p4_step1, step2, cumulative, maximum_trig


def validate_fixture(
    value: Any, base: Path = BASE, *, verify_D0_custody: bool = True,
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError("P6 fixture must be an object")
    if canonical_sha256(value) != FIXTURE_CANONICAL_SHA256:
        raise VerificationError("P6 fixture differs from the frozen canonical object")
    require_exact_keys(
        value,
        (
            "schema_version", "fixture_id", "direct_design_parent",
            "frozen_execution_relation", "adaptive_candidate",
            "full_domain_adaptive_rule", "exact_lazy_implementation",
            "outward_arithmetic", "deterministic_resource_caps",
            "deterministic_selection_caps", "host_supervisor_caps",
            "conditional_authority", "scientific_output_schema_budget", "scope",
        ),
        "P6 fixture",
    )
    if value["schema_version"] != 1 or value["fixture_id"] != FIXTURE_ID:
        raise SchemaError("unexpected P6 fixture identity")
    parent = value["direct_design_parent"]
    if (
        parent.get("commit_sha") != REQUIRED_PARENT_COMMIT
        or parent.get("D0_policy_id") != "MAJORANA-P6-E768-MAX-LAZY37-D0-V1"
        or parent.get("D0_report_available_to_runner") is not False
        or parent.get("formal_caps_derived_before_this_fixture") is not True
    ):
        raise VerificationError("P6 direct design-parent relation mismatch")
    if verify_D0_custody:
        if (
            parent.get("D0_policy_sha256")
            != file_sha256(Path(base) / D0_POLICY_NAME)
            or parent.get("D0_report_sha256")
            != file_sha256(Path(base) / D0_REPORT_NAME)
        ):
            raise VerificationError("P6 D0 custody mismatch")
    candidate = value["adaptive_candidate"]
    if (
        candidate.get("candidate_id") != CANDIDATE_ID
        or candidate.get("fresh_process_count") != 2
        or candidate.get("step1_threshold_Float64_bits_hex") != "3dd0000000000000"
        or candidate.get("lazy_anchor_Float64_bits_hex") != "3da0000000000000"
        or candidate.get("D0_control_is_not_a_formal_candidate") is not True
    ):
        raise VerificationError("P6 sole-candidate identity mismatch")
    relation = value["frozen_execution_relation"]
    if (
        relation.get("mapped_step_indices") != [1, 2]
        or relation.get("composite_count_per_step") != 512
        or relation.get("constituent_count_per_step") != 1152
        or relation.get("truncation_boundary_count_per_step") != BOUNDARY_COUNT
        or relation.get("same_process_step1_then_adaptive_step2") is not True
        or relation.get("step1_P3_fieldwise_conformance_required") is not True
        or relation.get("runner_must_not_read_any_result_or_D0_bytes") is not True
    ):
        raise VerificationError("P6 frozen execution relation mismatch")
    expected_base = {
        "P2": file_sha256(Path(base) / P2_FIXTURE_NAME),
        "P3": file_sha256(Path(base) / P3_FIXTURE_NAME),
        "P4": file_sha256(Path(base) / P4_FIXTURE_NAME),
        "P5": file_sha256(Path(base) / P5_FIXTURE_NAME),
    }
    if relation.get("required_base_fixture_sha256") != expected_base:
        raise VerificationError("P6 inherited fixture custody mismatch")
    arithmetic = value["outward_arithmetic"]
    if (
        arithmetic.get("trig_grid_denominator") != str(GRID)
        or arithmetic.get("defect_grid_denominator") != str(GRID)
        or arithmetic.get("maximum_BigInt_bit_length") != 2048
        or arithmetic.get("outward_integer_binary64_RNE_oracle_required") is not True
    ):
        raise VerificationError("P6 outward arithmetic mismatch")
    caps = value["deterministic_resource_caps"]
    if (
        caps.get("maximum_BigInt_bit_length") != 2048
        or caps.get("caps_are_checked_before_the_rejected_operation") is not True
        or caps.get("no_operation_occurs_after_the_first_deterministic_cap_event")
        is not True
    ):
        raise VerificationError("P6 deterministic cap semantics mismatch")
    _resource_cap_sections(value, Path(base))
    if value["deterministic_selection_caps"] != _EXPECTED_SELECTION_CAPS:
        raise VerificationError("P6 formal selection caps differ from D0")
    host = value["host_supervisor_caps"]
    for field in (
        "MemoryMax_bytes", "outer_safety_timeout_seconds",
        "maximum_stdout_bytes", "maximum_stderr_bytes",
    ):
        _positive_int(host.get(field), f"P6 host cap {field}")
    if (
        host.get("MemoryMax_bytes") != 2147483648
        or host.get("MemorySwapMax_bytes") != 0
        or host.get("RuntimeMaxSec") != "1800s"
        or host.get("outer_safety_timeout_seconds") != 1830
        or host.get("maximum_stdout_bytes") != 33554432
        or host.get("maximum_stderr_bytes") != 4096
        or host.get("systemd_user_scope_cgroup_v2_required") is not True
        or host.get("host_cap_failure_branch") != "INDETERMINATE"
    ):
        raise VerificationError("P6 host-supervisor policy mismatch")
    if _derive_persisted_result_byte_cap(value) != 67108864:
        raise VerificationError("P6 schema-derived result I/O caps mismatch")
    authority = value["conditional_authority"]
    if (
        Fraction(authority.get("candidate_local_allocation")) != STEP2_ALLOCATION
        or Fraction(authority.get("conditional_two_step_cumulative_allocation"))
        != CUMULATIVE_ALLOCATION
        or authority.get("candidate_qualification_is_outer_checker_only") is not True
        or authority.get("P3_E1_charge_multiplicity") != 1
    ):
        raise VerificationError("P6 conditional authority mismatch")
    adaptive = value["full_domain_adaptive_rule"]
    if (
        adaptive.get("boundary_count") != BOUNDARY_COUNT
        or adaptive.get("maximum_strictly_legal_local_ticks")
        != str(MAXIMUM_STRICT_LOCAL_TICKS)
        or adaptive.get("exact_fit_is_selected") is not True
        or adaptive.get("first_unaffordable_positive_row_stops_without_skipping")
        is not True
        or adaptive.get("future_prefix_budget_cannot_be_borrowed") is not True
    ):
        raise VerificationError("P6 adaptive scientific rule mismatch")
    if value["scope"] != RAW_SCOPE:
        raise VerificationError("P6 fixture scope mismatch")
    return value


_BRANCH_STATUS_DEFAULTS = {
    "CANDIDATE_QUALIFIED": ACCEPT_STATUS,
    "CANDIDATE_LOCAL_ALLOCATION_EXCEEDED": REJECT_LOCAL_STATUS,
    "CANDIDATE_LOCAL_AND_CUMULATIVE_ALLOCATIONS_EXCEEDED": REJECT_BOTH_STATUS,
    "DETERMINISTIC_POLICY_CAP_EXCEEDED": CAP_STATUS,
    "FAILED_P3_POST_REPLAY_CONFORMANCE": FAILED_CONFORMANCE_STATUS,
    "INDETERMINATE": INDETERMINATE_STATUS,
    "INVALID_REPLAY": INVALID_STATUS,
}


def validate_policy(
    value: Any, fixture: Mapping[str, Any] | None = None,
    base: Path = BASE, *, verify_D0_custody: bool = True,
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError("P6 policy must be an object")
    if canonical_sha256(value) != POLICY_CANONICAL_SHA256:
        raise VerificationError("P6 policy differs from the frozen canonical object")
    if (
        value["schema_version"] != 1
        or value["policy_id"] != "MAJORANA-P6-S0-E768-MAX-LAZY37-HARDENING-V1"
        or value["required_fixture_id"] != FIXTURE_ID
        or value["required_direct_design_parent_commit"] != REQUIRED_PARENT_COMMIT
    ):
        raise SchemaError("unexpected P6 policy identity")
    candidate = value.get("formal_candidate_design", {})
    if (
        candidate.get("formal_candidates") != [CANDIDATE_ID]
        or candidate.get("fresh_process_count") != 2
        or candidate.get("D0_control_is_excluded") is not True
    ):
        raise VerificationError("P6 formal candidate policy mismatch")
    parent = value.get("parent_authority_and_telescoping", {})
    if (
        parent.get("P3_E1_charge_multiplicity") != 1
        or parent.get("P4_or_P5_step2_error_is_not_inherited") is not True
        or parent.get("D0_report_is_not_a_runner_input") is not True
    ):
        raise VerificationError("P6 parent/telescoping policy mismatch")
    allocation = value["allocation_enforcement"]
    if (
        Fraction(allocation.get("candidate_step2_local_allocation"))
        != STEP2_ALLOCATION
        or Fraction(allocation.get("conditional_two_step_cumulative_allocation"))
        != CUMULATIVE_ALLOCATION
        or allocation.get("equality_is_failure") is not True
        or allocation.get("candidate_qualified_iff_local_and_cumulative_pass") is not True
        or allocation.get("allocation_comparisons_use_exact_integer_cross_multiplication_only")
        is not True
        or allocation.get("outer_checker_alone_composes_P3_E1")
        is not True
    ):
        raise VerificationError("P6 allocation policy mismatch")
    provenance = value["D0_cap_provenance"]
    if (
        provenance.get("D0_report_commit_sha") != REQUIRED_PARENT_COMMIT
        or provenance.get("formal_candidates_were_frozen_before_D0") != [CANDIDATE_ID]
        or provenance.get("D0_report_bytes_are_forbidden_from_runner_staging")
        is not True
        or provenance.get("D0_report_has_no_scientific_authority")
        is not True
    ):
        raise VerificationError("P6 D0 provenance policy mismatch")
    if verify_D0_custody:
        if (
            provenance.get("D0_policy_sha256")
            != file_sha256(Path(base) / D0_POLICY_NAME)
            or provenance.get("D0_report_sha256")
            != file_sha256(Path(base) / D0_REPORT_NAME)
        ):
            raise VerificationError("P6 D0 provenance custody mismatch")
    truth = value["qualification_and_terminal_truth_table"]
    branches = {
        row.get("branch"): row.get("maximum_status")
        for row in truth.get("legal_terminal_branches", [])
        if isinstance(row, dict)
    }
    if branches != _BRANCH_STATUS_DEFAULTS:
        raise VerificationError("P6 terminal branch/status map mismatch")
    visibility = value["runner_visibility_and_precommit_boundary"]
    if (
        visibility.get("runner_must_not_read_any_parent_result_or_certificate")
        is not True
        or visibility.get("runner_must_not_read_D0_policy_or_report_bytes") is not True
        or visibility.get("outer_checker_may_read_result_bytes_only_after_both_raw_processes_finish")
        is not True
        or visibility.get("formal_precommit_must_exclude_P6_result_artifacts")
        is not True
        or visibility.get(
            "formal_stage_contains_only_the_standalone_P6_runner_P0_runtime_"
            "P2_P3_P4_sources_and_fixtures_and_P5_workload_fixture"
        ) is not True
        or not isinstance(visibility.get("forbidden_formal_result_pins"), list)
    ):
        raise VerificationError("P6 result-blind runner policy mismatch")
    determinism = value["result_determinism_and_signed_zero"]
    if (
        determinism.get("both_raw_transcripts_must_be_byte_identical")
        is not True
        or determinism.get("step1_fieldwise_conformance_is_not_replaced_by_a_single_opaque_digest")
        is not True
        or determinism.get("checker_replays_the_frozen_ordered_ComplexF64_times_Complex_Int64_unit_Fock_loop")
        is not True
        or determinism.get("phase_only_or_real_value_only_Fock_shortcuts_are_forbidden")
        is not True
        or determinism.get("the_P4_signed_zero_v1_failure_mode_is_an_explicit_fail_closed_regression")
        is not True
    ):
        raise VerificationError("P6 signed-zero/determinism policy mismatch")
    if fixture is not None:
        if value["deterministic_resource_caps"] != fixture["deterministic_resource_caps"]:
            raise VerificationError("P6 fixture/policy step2 caps differ")
        if value["deterministic_selection_caps"] != fixture["deterministic_selection_caps"]:
            raise VerificationError("P6 fixture/policy selection caps differ")
        for key, expected in fixture["host_supervisor_caps"].items():
            if value["host_supervisor_caps"].get(key) != expected:
                raise VerificationError(f"P6 fixture/policy host cap differs: {key}")
        if value["scientific_output_schema_budget"] != fixture[
            "scientific_output_schema_budget"
        ]:
            raise VerificationError("P6 fixture/policy output budget differs")
    return value


def validate_precommit_contract(
    value: Any, base: Path = BASE, *, verify_source_files: bool = True,
    verify_D0_custody: bool = True,
) -> Mapping[str, Any]:
    base = Path(base)
    if not isinstance(value, dict):
        raise SchemaError("P6 precommit contract must be an object")
    require_exact_keys(
        value,
        (
            "schema_version", "contract_type", "self_relative_path",
            "required_parent_commit", "result_artifacts_required_absent",
            "forbidden_formal_result_pins", "source_files",
            "runner_staged_files", "runner_forbidden_paths",
        ),
        "P6 precommit contract",
    )
    if (
        value["schema_version"] != 1
        or value["contract_type"] != PRECOMMIT_CONTRACT_TYPE
        or value["self_relative_path"] != PRECOMMIT_CONTRACT_NAME
        or value["required_parent_commit"] != REQUIRED_PARENT_COMMIT
    ):
        raise VerificationError("P6 precommit identity or parent mismatch")
    fixture = validate_fixture(
        load_json(base / FIXTURE_NAME), base,
        verify_D0_custody=verify_D0_custody,
    )
    policy = validate_policy(
        load_json(base / POLICY_NAME), fixture, base,
        verify_D0_custody=verify_D0_custody,
    )
    forbidden_pins = policy["runner_visibility_and_precommit_boundary"][
        "forbidden_formal_result_pins"
    ]
    if value["forbidden_formal_result_pins"] != forbidden_pins:
        raise VerificationError("P6 forbidden result pins mismatch")
    if tuple(value["result_artifacts_required_absent"]) != (
        RESULT_CONTRACT_NAME, CERTIFICATE_NAME, RESULT_TEST_NAME,
    ):
        raise VerificationError("P6 result artifact absence set mismatch")
    if tuple(value["runner_staged_files"]) != RUNNER_STAGED_PATHS:
        raise VerificationError("P6 runner staging allowlist mismatch")
    if tuple(value["runner_forbidden_paths"]) != RUNNER_FORBIDDEN_PATHS:
        raise VerificationError("P6 runner forbidden path set mismatch")
    rows = value["source_files"]
    if not isinstance(rows, list):
        raise SchemaError("P6 source_files must be an array")
    paths: list[str] = []
    for row in rows:
        require_exact_keys(row, ("relative_path", "size_bytes", "sha256"), "P6 source row")
        relative = row["relative_path"]
        if (
            not isinstance(relative, str) or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise SchemaError("invalid P5 source relative path")
        if type(row["size_bytes"]) is not int or row["size_bytes"] < 0:
            raise SchemaError("invalid P5 source size")
        require_sha256(row["sha256"], f"P6 source hash {relative}")
        if verify_source_files:
            path = base / relative
            if path.is_symlink() or not path.is_file():
                raise VerificationError(f"P6 source is not a regular file: {relative}")
            if path.stat().st_size != row["size_bytes"] or file_sha256(path) != row["sha256"]:
                raise VerificationError(f"P6 source custody mismatch: {relative}")
        paths.append(relative)
    if tuple(paths) != PRECOMMIT_SOURCE_PATHS:
        raise VerificationError("P6 source custody allowlist mismatch")
    if not set(RUNNER_STAGED_PATHS).issubset(paths):
        raise VerificationError("P6 runner stage is outside source custody")
    if set(RUNNER_STAGED_PATHS) & set(RUNNER_FORBIDDEN_PATHS):
        raise VerificationError("P6 runner stage exposes a forbidden result")
    return value


_SIGNED_ZERO_MICRO_ORACLE_SHA256 = (
    "323caca70bb0131db1ac554beaa99ffe4b4d9927ec448c83db5a9b11dd9d70c4"
)
_signed_zero_micro_oracle_checked = False


def _verify_signed_zero_micro_oracle() -> None:
    """Pin the P4 v2 ordered-Complex identity and signed-zero repair."""

    global _signed_zero_micro_oracle_checked
    if _signed_zero_micro_oracle_checked:
        return
    with _P4_GLOBAL_LOCK:
        if _signed_zero_micro_oracle_checked:
            return
        occupied = P3._neel_gamma_mask()
        if (
            P3._upstream_fock_real_bits(0x17C, occupied) != 0
            or P4._upstream_fock_real_bits(0x17C, occupied) != SIGN_MASK
            or P4._upstream_fock_real_bits(0x53C, occupied) != 0
            or P4._complex_mul_bits(
                (SIGN_MASK, 0xBFF0000000000000),
                (0x3FF0000000000000, 0),
            ) != (0, 0xBFF0000000000000)
        ):
            raise VerificationError("P6 signed-zero/identity micro-oracle mismatch")
        digest = hashlib.sha256()
        for mask in range(1 << 16):
            bits = P4._upstream_fock_real_bits(mask, occupied)
            digest.update(f"{mask:x}\t{bits:016x}\n".encode("ascii"))
        if digest.hexdigest() != _SIGNED_ZERO_MICRO_ORACLE_SHA256:
            raise VerificationError("P6 signed-zero micro-oracle digest mismatch")
        _signed_zero_micro_oracle_checked = True


def _selection_rank_key(row: Mapping[str, int]) -> tuple[int, int, int]:
    return (
        int(row["point_abs_ticks"]), int(row["abs_bits"]), int(row["mask"]),
    )


def brute_force_select(
    rows: Sequence[Mapping[str, int]], available: int,
) -> list[Mapping[str, int]]:
    if type(available) is not int or available < 0:
        raise SchemaError("P6 brute-force available ticks must be nonnegative")
    result: list[Mapping[str, int]] = []
    remaining = available
    for row in sorted(rows, key=_selection_rank_key):
        cost = int(row["point_abs_ticks"])
        if cost < 0:
            raise SchemaError("P6 row cost must be nonnegative")
        if cost > remaining:
            break
        result.append(row)
        remaining -= cost
    return result


def lazy_select(
    rows: Sequence[Mapping[str, int]], available: int,
) -> list[Mapping[str, int]]:
    if type(available) is not int or available < 0:
        raise SchemaError("P6 lazy available ticks must be nonnegative")
    tier1 = sorted(
        (row for row in rows if int(row["abs_bits"]) < LAZY_ANCHOR_BITS),
        key=_selection_rank_key,
    )
    result: list[Mapping[str, int]] = []
    remaining = available
    for row in tier1:
        cost = int(row["point_abs_ticks"])
        if cost > remaining:
            return result
        result.append(row)
        remaining -= cost
    if remaining == 0:
        return result
    tier2 = sorted(
        (
            row for row in rows
            if int(row["abs_bits"]) >= LAZY_ANCHOR_BITS
            and int(row["point_abs_ticks"]) <= remaining
        ),
        key=_selection_rank_key,
    )
    for row in tier2:
        cost = int(row["point_abs_ticks"])
        if cost > remaining:
            break
        result.append(row)
        remaining -= cost
    return result


def _candidate_descriptor(candidate_id: str) -> dict[str, Any]:
    if candidate_id != CANDIDATE_ID:
        raise SchemaError("unknown P6 candidate")
    return {
        "candidate_id": candidate_id,
        "identity": "step1_fixed_2^-34_then_step2_E768_MAX_LAZY37_V1",
        "required_fresh_process_count": 2,
        "step1_threshold_exponent": 34,
        "step1_threshold_rational": "1/17179869184",
        "step1_threshold_Float64_bits_hex": "3dd0000000000000",
        "adaptive_rule_id": CANDIDATE_ID,
        "boundary_count": BOUNDARY_COUNT,
        "local_allocation": "1/400000",
        "lazy_anchor_threshold_exponent": 37,
        "lazy_anchor_Float64_bits_hex": "3da0000000000000",
        "lazy_anchor_is_not_a_scientific_eligibility_gate": True,
        "full_domain_longest_affordable_prefix": True,
        "step1_path_is_not_rethresholded": True,
        "D0_control_candidate_excluded": True,
    }


def _state_descriptor(state: Mapping[int, int]) -> dict[str, Any]:
    return P4._state_descriptor(state)


def _empty_selection_tracker(caps: Mapping[str, int]) -> dict[str, Any]:
    if dict(caps) != _EXPECTED_SELECTION_CAPS:
        raise VerificationError("P6 oracle selection caps drift")
    return {
        "caps": dict(caps),
        "total_ranking_scan_term_visits": 0,
        "total_sort_work_items": 0,
        "total_tick_evaluations": 0,
        "total_selected_membership_insertions": 0,
        "peak_ranking_buffer_terms": 0,
        "total_selection_work_units": 0,
        "completed_selection_boundary_count": 0,
        "_pending_selected_cost": {},
    }


def _selection_cap_context(boundary_index: int, operation: str) -> dict[str, Any]:
    return {"boundary_index": boundary_index, "operation": operation}


def _observe_selection_peak(
    tracker: MutableMapping[str, Any], size: int, boundary_index: int,
    operation: str,
) -> None:
    attempted = max(tracker["peak_ranking_buffer_terms"], size)
    limit = tracker["caps"]["maximum_peak_ranking_buffer_terms"]
    if attempted > limit:
        raise P4._CapExceeded(
            step_index=2, cap_name="maximum_peak_ranking_buffer_terms",
            cap_scope="step", limit=limit, attempted=attempted,
            context=_selection_cap_context(boundary_index, operation),
        )
    tracker["peak_ranking_buffer_terms"] = attempted


def _charge_selection(
    tracker: MutableMapping[str, Any], field: str, amount: int,
    cap_name: str, boundary_index: int, operation: str,
) -> None:
    if amount < 0:
        raise VerificationError("negative P6 selection charge")
    if amount == 0:
        return
    attempted = tracker[field] + amount
    limit = tracker["caps"][cap_name]
    context = _selection_cap_context(boundary_index, operation)
    if attempted > limit:
        raise P4._CapExceeded(
            step_index=2, cap_name=cap_name, cap_scope="step",
            limit=limit, attempted=attempted, context=context,
        )
    work_attempted = tracker["total_selection_work_units"] + amount
    work_limit = tracker["caps"]["maximum_total_selection_work_units"]
    if work_attempted > work_limit:
        raise P4._CapExceeded(
            step_index=2, cap_name="maximum_total_selection_work_units",
            cap_scope="step", limit=work_limit, attempted=work_attempted,
            context=context,
        )
    tracker[field] = attempted
    tracker["total_selection_work_units"] = work_attempted


def _p6_select_rows_for_boundary(
    *, state: Mapping[int, int], ticks: Mapping[str, int],
    boundary_index: int, maximum_bits: int,
    selection_tracker: MutableMapping[str, Any],
) -> list[tuple[int, int]]:
    if maximum_bits != 2048 or not 0 <= boundary_index < BOUNDARY_COUNT:
        raise VerificationError("P6 oracle boundary context drift")
    row_count = len(state)
    _observe_selection_peak(
        selection_tracker, row_count, boundary_index, "postmerge_snapshot_buffer",
    )
    _charge_selection(
        selection_tracker, "total_ranking_scan_term_visits", row_count,
        "maximum_ranking_scan_term_visits", boundary_index,
        "postmerge_snapshot_scan",
    )
    rows = [
        {"mask": mask, "bits": bits, "abs_bits": bits & ~SIGN_MASK}
        for mask, bits in state.items()
    ]
    if len(rows) != row_count:
        raise VerificationError("P6 oracle snapshot size changed during materialization")
    target = ((boundary_index + 1) * MAXIMUM_STRICT_LOCAL_TICKS) // BOUNDARY_COUNT
    current = sum(ticks.values())
    if current < 0:
        raise VerificationError("negative P6 local ledger")
    available = max(0, target - current)

    tier1: list[dict[str, int]] = []
    for snapshot in rows:
        if snapshot["abs_bits"] >= LAZY_ANCHOR_BITS:
            continue
        _charge_selection(
            selection_tracker, "total_tick_evaluations", 1,
            "maximum_tick_evaluations", boundary_index, "tier1_row_cost",
        )
        tier1.append({
            **snapshot,
            "point_abs_ticks": P3.drop_defect_upper_ticks(snapshot["bits"]),
        })
    _observe_selection_peak(
        selection_tracker, len(tier1), boundary_index, "tier1_rank_sort",
    )
    _charge_selection(
        selection_tracker, "total_sort_work_items", len(tier1),
        "maximum_sort_input_items", boundary_index, "tier1_rank_sort",
    )
    tier1.sort(key=_selection_rank_key)
    lazy_selected: list[Mapping[str, int]] = []
    remaining = available
    tier1_complete = True
    for row in tier1:
        if row["point_abs_ticks"] > remaining:
            tier1_complete = False
            break
        lazy_selected.append(row)
        remaining -= row["point_abs_ticks"]
    _charge_selection(
        selection_tracker, "total_selected_membership_insertions",
        len(lazy_selected),
        "maximum_selected_membership_insertions", boundary_index,
        "selected_membership_insertions",
    )

    if tier1_complete and remaining > 0:
        _charge_selection(
            selection_tracker, "total_ranking_scan_term_visits", len(rows),
            "maximum_ranking_scan_term_visits", boundary_index,
            "tier2_original_snapshot_rescan",
        )
        outside: list[dict[str, int]] = []
        for snapshot in rows:
            if snapshot["abs_bits"] < LAZY_ANCHOR_BITS:
                continue
            _charge_selection(
                selection_tracker, "total_tick_evaluations", 1,
                "maximum_tick_evaluations", boundary_index, "tier2_row_cost",
            )
            outside.append({
                **snapshot,
                "point_abs_ticks": P3.drop_defect_upper_ticks(snapshot["bits"]),
            })
        tier2 = [row for row in outside if row["point_abs_ticks"] <= remaining]
        _observe_selection_peak(
            selection_tracker, len(tier2), boundary_index, "tier2_rank_sort",
        )
        _charge_selection(
            selection_tracker, "total_sort_work_items", len(tier2),
            "maximum_sort_input_items", boundary_index, "tier2_rank_sort",
        )
        tier2.sort(key=_selection_rank_key)
        selected_tier2: list[Mapping[str, int]] = []
        for row in tier2:
            if row["point_abs_ticks"] > remaining:
                break
            selected_tier2.append(row)
            remaining -= row["point_abs_ticks"]
        _charge_selection(
            selection_tracker, "total_selected_membership_insertions",
            len(selected_tier2), "maximum_selected_membership_insertions",
            boundary_index, "selected_membership_insertions",
        )
        lazy_selected.extend(selected_tier2)
    brute = brute_force_select([
        {
            **row,
            "point_abs_ticks": P3.drop_defect_upper_ticks(row["bits"]),
        }
        for row in rows
    ], available)
    if [
        (row["mask"], row["bits"]) for row in lazy_selected
    ] != [
        (row["mask"], row["bits"]) for row in brute
    ]:
        raise VerificationError("P6 lazy/full-domain selection mismatch")
    selection_tracker["_pending_selected_cost"][boundary_index] = sum(
        int(row["point_abs_ticks"]) for row in brute
    )
    # The brute-force full-domain reconstruction is authoritative.  The lazy
    # path above exists only to reproduce runner resources and prove equality.
    return sorted((int(row["mask"]), int(row["bits"])) for row in brute)


def _p6_complete_selection_boundary(
    selection_tracker: MutableMapping[str, Any], boundary_index: int,
    transition_drop_ticks: int,
) -> None:
    expected = selection_tracker["_pending_selected_cost"].pop(boundary_index, None)
    if expected is None or expected != transition_drop_ticks:
        raise VerificationError("P6 selected cost differs from drop ledger")
    selection_tracker["completed_selection_boundary_count"] += 1
    if selection_tracker["completed_selection_boundary_count"] > BOUNDARY_COUNT:
        raise VerificationError("too many P6 selection boundaries")


def _public_selection_resources(tracker: Mapping[str, Any]) -> dict[str, int]:
    fields = (
        "total_ranking_scan_term_visits", "total_sort_work_items",
        "total_tick_evaluations", "total_selected_membership_insertions",
        "peak_ranking_buffer_terms", "total_selection_work_units",
        "completed_selection_boundary_count",
    )
    result = {field: int(tracker[field]) for field in fields}
    if result["total_selection_work_units"] != sum(
        result[field] for field in fields[:4]
    ):
        raise VerificationError("P6 selection work identity failed")
    return result


def _build_adaptive_step_oracle():
    source = inspect.getsource(P4._run_step_oracle)
    source = source.replace(
        "def _run_step_oracle(", "def _run_p6_adaptive_step_oracle(", 1
    )
    signature = (
        "    maximum_bits: int, input_state: Mapping[str, Any],\n"
        ") -> tuple[dict[str, Any], dict[int, int]]:"
    )
    replacement = (
        "    maximum_bits: int, input_state: Mapping[str, Any],\n"
        "    selection_tracker: MutableMapping[str, Any],\n"
        ") -> tuple[dict[str, Any], dict[int, int]]:"
    )
    if source.count(signature) != 1:
        raise RuntimeError("P4 oracle signature drift")
    source = source.replace(signature, replacement)
    drop_needle = """                        dropped = sorted(
                            (mask, bits) for mask, bits in state.items()
                            if (bits & ~SIGN_MASK) < EPSILON_BITS
                        )"""
    drop_replacement = """                        dropped = _p6_select_rows_for_boundary(
                            state=state, ticks=ticks,
                            boundary_index=public[\"boundary_index_after\"],
                            maximum_bits=maximum_bits,
                            selection_tracker=selection_tracker,
                        )"""
    if source.count(drop_needle) != 1:
        raise RuntimeError("P4 oracle drop block drift")
    source = source.replace(drop_needle, drop_replacement)
    completion_needle = """                        cumulative_drop_bits = P3._rne_add_bits(
                            cumulative_drop_bits, diagnostic_increment_bits,
                        )"""
    completion_replacement = """                        _p6_complete_selection_boundary(
                            selection_tracker, public[\"boundary_index_after\"],
                            transition_drop_ticks,
                        )
                        cumulative_drop_bits = P3._rne_add_bits(
                            cumulative_drop_bits, diagnostic_increment_bits,
                        )"""
    if source.count(completion_needle) != 1:
        raise RuntimeError("P4 oracle completion block drift")
    source = source.replace(completion_needle, completion_replacement)
    namespace = dict(P4.__dict__)
    namespace.update({
        "_p6_select_rows_for_boundary": _p6_select_rows_for_boundary,
        "_p6_complete_selection_boundary": _p6_complete_selection_boundary,
        "MutableMapping": MutableMapping,
    })
    exec(compile(source, "<p6-adaptive-step-oracle>", "exec"), namespace)
    return namespace["_run_p6_adaptive_step_oracle"]


_RUN_P6_ADAPTIVE_STEP_ORACLE = None


def _get_p6_adaptive_step_oracle():
    """Build the independent adaptive oracle only after raw execution."""

    global _RUN_P6_ADAPTIVE_STEP_ORACLE
    if _RUN_P6_ADAPTIVE_STEP_ORACLE is None:
        _RUN_P6_ADAPTIVE_STEP_ORACLE = _build_adaptive_step_oracle()
    return _RUN_P6_ADAPTIVE_STEP_ORACLE


def replay_candidate_oracle(
    trig_table: Mapping[str, Any], fixture: Mapping[str, Any],
    candidate_id: str, base: Path = BASE,
) -> dict[str, Any]:
    """Independently reconstruct the sole result-blind adaptive candidate."""

    base = Path(base)
    if candidate_id not in CANDIDATE_ORDER:
        raise SchemaError("unknown P6 oracle candidate")
    trig = P3._validate_trig_table(trig_table)
    schedule = P3.expected_schedule()
    step1_caps, step2_caps, cumulative_caps, maximum_trig = _resource_cap_sections(
        fixture, base,
    )
    if len(trig) != maximum_trig:
        raise VerificationError("P6 raw trigonometric table exceeds its frozen cap")
    maximum_bits = fixture["outward_arithmetic"]["maximum_BigInt_bit_length"]
    state = P3._initial_state()
    initial_descriptor = _state_descriptor(state)
    p3_fixture_path = base / P3_FIXTURE_NAME
    p3_fixture = load_json(p3_fixture_path)
    step1_input = {
        "term_count": initial_descriptor["term_count"],
        "term_stream_sha256": initial_descriptor["term_stream_sha256"],
        "P3_fixture_id": p3_fixture["fixture_id"],
        "P3_fixture_sha256": file_sha256(p3_fixture_path),
        "P3_fixture_canonical_sha256": canonical_sha256(p3_fixture),
    }
    cumulative = P4._empty_cumulative_counters()
    with _P4_GLOBAL_LOCK:
        previous_epsilon = P4.EPSILON_BITS
        try:
            P4.EPSILON_BITS = STEP1_THRESHOLD_BITS
            step1, state = P4._run_step_oracle(
                step_index=1, state=state, trig=trig, schedule=schedule,
                step_caps=step1_caps, cumulative_caps=cumulative_caps,
                cumulative=cumulative, maximum_bits=maximum_bits,
                input_state=step1_input,
            )
            # Step-specific mutation is restored before the candidate setting;
            # the outer finally also covers every exception path.
            P4.EPSILON_BITS = previous_epsilon
            step2 = None
            link = None
            selection_tracker = _empty_selection_tracker(
                fixture["deterministic_selection_caps"]
            )
            if step1["execution"]["cap_event"] is None:
                if step1["final_state"] is None:
                    raise VerificationError("completed P6 step1 lacks a final state")
                step2_input = _state_descriptor(state)
                if (
                    step2_input["term_count"]
                    != step1["final_state"]["retained_term_count"]
                    or step2_input["term_stream_sha256"]
                    != step1["final_state"]["term_stream_sha256"]
                ):
                    raise VerificationError("P6 oracle step boundary does not link")
                state = dict(state)
                step2, state = _get_p6_adaptive_step_oracle()(
                    step_index=2, state=state, trig=trig, schedule=schedule,
                    step_caps=step2_caps, cumulative_caps=cumulative_caps,
                    cumulative=cumulative, maximum_bits=maximum_bits,
                    input_state=step2_input,
                    selection_tracker=selection_tracker,
                )
                link = {
                    "same_process": True,
                    "no_serialization": True,
                    "step1_output_term_count": step1["final_state"][
                        "retained_term_count"
                    ],
                    "step1_output_term_stream_sha256": step1["final_state"][
                        "term_stream_sha256"
                    ],
                    "step2_input_term_count": step2_input["term_count"],
                    "step2_input_term_stream_sha256": step2_input[
                        "term_stream_sha256"
                    ],
                }
        finally:
            P4.EPSILON_BITS = previous_epsilon
    return {
        "candidate": _candidate_descriptor(candidate_id),
        "step1": step1,
        "step_boundary_link": link,
        "step2": step2,
        "selection_resources": _public_selection_resources(selection_tracker),
    }


def _assert_fieldwise_equal(actual: Any, expected: Any, context: str) -> None:
    P4._assert_fieldwise_equal(actual, expected, context)


def validate_raw_witness(
    witness: Any, fixture: Mapping[str, Any], runtime_lock: Mapping[str, Any],
    expected_candidate_id: str | None = None, base: Path = BASE,
) -> Mapping[str, Any]:
    """Validate runner-only evidence without opening D0 or P3/P4 results."""

    base = Path(base)
    _verify_signed_zero_micro_oracle()
    if not isinstance(witness, dict):
        raise SchemaError("P6 raw witness must be an object")
    require_exact_keys(
        witness,
        (
            "schema_version", "witness_type", "fixture_id", "fixture_sha256",
            "fixture_canonical_sha256", "inherited_P4_fixture_sha256",
            "inherited_P4_fixture_canonical_sha256",
            "inherited_P5_fixture_sha256",
            "inherited_P5_fixture_canonical_sha256",
            "inherited_P3_fixture_sha256",
            "inherited_P3_fixture_canonical_sha256",
            "inherited_P2_fixture_sha256",
            "inherited_P2_fixture_canonical_sha256", "runtime", "upstream",
            "initial_observable", "schedule", "trig_table", "candidate",
            "step1", "step_boundary_link", "step2",
            "selection_resources", "scope",
        ),
        "P6 raw witness",
    )
    if (
        witness["schema_version"] != 1
        or witness["witness_type"] != RAW_WITNESS_TYPE
        or witness["fixture_id"] != fixture["fixture_id"]
    ):
        raise SchemaError("unexpected P6 raw witness identity")
    fixture_path = base / FIXTURE_NAME
    if (
        witness["fixture_sha256"] != file_sha256(fixture_path)
        or witness["fixture_canonical_sha256"] != canonical_sha256(fixture)
    ):
        raise VerificationError("P6 raw fixture custody mismatch")
    p5_fixture_path = base / P5_FIXTURE_NAME
    p5_fixture = load_json(p5_fixture_path)
    P5.validate_fixture(p5_fixture, base)
    if (
        witness["inherited_P5_fixture_sha256"] != file_sha256(p5_fixture_path)
        or witness["inherited_P5_fixture_canonical_sha256"]
        != canonical_sha256(p5_fixture)
    ):
        raise VerificationError("P6 raw inherited P5 fixture custody mismatch")
    with _p4_module_base(base):
        for prefix, name, validator in (
            ("P4", P4_FIXTURE_NAME, P4.validate_fixture),
            ("P3", P3_FIXTURE_NAME, P3.validate_fixture),
            ("P2", P2_FIXTURE_NAME, P2.validate_fixture),
        ):
            path = base / name
            inherited = load_json(path)
            validator(inherited)
            if (
                witness[f"inherited_{prefix}_fixture_sha256"] != file_sha256(path)
                or witness[f"inherited_{prefix}_fixture_canonical_sha256"]
                != canonical_sha256(inherited)
            ):
                raise VerificationError(
                    f"P6 raw inherited {prefix} fixture custody mismatch"
                )
    if witness["runtime"] != P2._expected_runtime(runtime_lock):
        raise VerificationError("P6 raw runtime custody mismatch")
    if witness["upstream"] != P2._expected_upstream(runtime_lock):
        raise VerificationError("P6 raw upstream custody mismatch")
    if witness["initial_observable"] != P2.expected_initial_observable():
        raise VerificationError("P6 raw initial observable mismatch")
    if witness["schedule"] != P3.expected_schedule():
        raise VerificationError("P6 raw schedule mismatch")
    if witness["scope"] != RAW_SCOPE or witness["scope"] != fixture["scope"]:
        raise VerificationError("P6 raw scope exceeds execution-only authority")
    candidate_id = witness["candidate"].get("candidate_id") \
        if isinstance(witness["candidate"], dict) else None
    if candidate_id not in CANDIDATE_ORDER:
        raise SchemaError("P6 raw candidate identity is not allowed")
    if expected_candidate_id is not None and candidate_id != expected_candidate_id:
        raise VerificationError("P6 raw candidate differs from its outer process binding")
    oracle = replay_candidate_oracle(
        witness["trig_table"], fixture, candidate_id, base,
    )
    for field in (
        "candidate", "step1", "step_boundary_link", "step2",
        "selection_resources",
    ):
        _assert_fieldwise_equal(
            witness[field], oracle[field], f"P6 {candidate_id} raw {field}",
        )
    step1 = witness["step1"]
    step2 = witness["step2"]
    if step1["execution"]["cap_event"] is not None:
        if step2 is not None or witness["step_boundary_link"] is not None:
            raise VerificationError("P6 capped step1 has an attempted step2")
    else:
        if step2 is None or witness["step_boundary_link"] is None:
            raise VerificationError("P6 completed step1 lacks its same-process step2")
        link = witness["step_boundary_link"]
        if (
            link["same_process"] is not True or link["no_serialization"] is not True
            or link["step1_output_term_count"] != link["step2_input_term_count"]
            or link["step1_output_term_stream_sha256"]
            != link["step2_input_term_stream_sha256"]
        ):
            raise VerificationError("P6 raw step boundary is not same-process linked")
    return witness


def _step1_p3_projection(raw: Mapping[str, Any], base: Path = BASE) -> dict[str, Any]:
    """Project a P5 candidate's complete prefix into the exact P3 schema."""

    if raw["step1"]["execution"]["cap_event"] is not None:
        raise VerificationError("capped P5 step1 has no complete P3 projection")
    p4_shim = {
        "steps": [raw["step1"]],
        "inherited_P2_fixture_sha256": raw["inherited_P2_fixture_sha256"],
        "inherited_P2_fixture_canonical_sha256": raw[
            "inherited_P2_fixture_canonical_sha256"
        ],
        "runtime": raw["runtime"],
        "upstream": raw["upstream"],
        "initial_observable": raw["initial_observable"],
        "schedule": raw["schedule"],
        "trig_table": raw["trig_table"],
    }
    with _p4_module_base(Path(base)):
        return P4._step1_p3_projection(p4_shim, Path(base))


def _formal_envelope_from_d0(
    report: Mapping[str, Any],
) -> tuple[dict[str, int], dict[str, int], dict[str, Any]]:
    envelope = report.get("formal_resource_envelope")
    if (
        not isinstance(envelope, dict)
        or envelope.get("status") != "ESTABLISHED_FOR_FUTURE_S0_PRECOMMIT"
    ):
        raise VerificationError("P6 D0 formal resource envelope is not established")
    root = envelope.get("formal_step2_caps")
    selection = envelope.get("formal_selection_caps")
    host = envelope.get("formal_host_caps")
    if not isinstance(root, dict) or not isinstance(selection, dict) or not isinstance(host, dict):
        raise SchemaError("P6 D0 formal resource envelope shape mismatch")
    step2 = {
        "maximum_current_terms_before_constituent":
            root["maximum_step2_current_terms_before_constituent"],
        "maximum_premerge_terms": root["maximum_step2_premerge_terms"],
        "maximum_boundary_retained_terms":
            root["maximum_step2_boundary_retained_terms"],
        "maximum_cap_scan_term_visits": root["maximum_step2_cap_scan_term_visits"],
        "maximum_propagation_term_visits":
            root["maximum_step2_propagation_term_visits"],
        "maximum_truncation_term_visits":
            root["maximum_step2_truncation_term_visits"],
        "maximum_final_evaluation_term_visits":
            root["maximum_step2_final_retained_terms"],
        "maximum_total_charged_term_visits":
            root["maximum_step2_total_P2_charged_term_visits"],
        "maximum_anticommuting_events":
            root["maximum_step2_anticommuting_events"],
        "maximum_product_defect_events": root["maximum_step2_product_defect_events"],
        "maximum_merge_defect_events": root["maximum_step2_merge_defect_events"],
        "maximum_drop_defect_events": root["maximum_step2_drop_defect_events"],
        "maximum_accuracy_charged_events":
            root["maximum_step2_accuracy_charged_events"],
        "maximum_total_P2_plus_accuracy_charged_events":
            root["maximum_step2_total_P2_plus_accuracy_charged_events"],
        "maximum_composites": 512,
        "maximum_constituents": 1152,
        "maximum_truncation_boundaries": BOUNDARY_COUNT,
    }
    return step2, dict(selection), dict(host)


def _git_committed_bytes(
    base: Path, commit: str, relative: str,
) -> bytes:
    repo, base_relative = P2._repo_and_base_relative(Path(base))
    return P2._run_git(
        repo, "show", f"{commit}:{(base_relative / relative).as_posix()}",
    ).stdout


def _verify_precommit_changed_path_allowlist(
    repo: Path, base_relative: Path, commit: str,
) -> list[str]:
    changed = tuple(sorted(filter(None, P2._run_git(
        repo, "diff-tree", "--no-commit-id", "--name-only", "-r",
        "--no-renames", commit,
    ).stdout.decode().splitlines())))
    expected = tuple(sorted(
        (base_relative / relative).as_posix()
        for relative in PRECOMMIT_CHANGED_PATHS
    ))
    if changed != expected:
        raise VerificationError(
            "P6 precommit changed-path set differs from the exact six-file allowlist"
        )
    return list(changed)


def _verify_design_parent_and_nonnumeric_lineage(
    fixture: Mapping[str, Any], policy: Mapping[str, Any], base: Path = BASE,
) -> tuple[
    Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]
]:
    """Verify D0/P5 lineage and P3 pins without opening the P3 result."""

    base = Path(base)
    repo, _base_relative = P2._repo_and_base_relative(base)
    resolved = P2._run_git(repo, "rev-parse", REQUIRED_PARENT_COMMIT).stdout.decode().strip()
    if resolved != REQUIRED_PARENT_COMMIT:
        raise VerificationError("P6 direct design parent does not resolve exactly")
    p5_is_ancestor = P2._run_git(
        repo, "merge-base", "--is-ancestor", P5_RESULT_COMMIT,
        REQUIRED_PARENT_COMMIT, check=False,
    )
    p3_is_ancestor = P2._run_git(
        repo, "merge-base", "--is-ancestor", P3_RESULT_COMMIT,
        P4_RESULT_COMMIT, check=False,
    )
    if p5_is_ancestor.returncode != 0 or p3_is_ancestor.returncode != 0:
        raise VerificationError("P6 parent ancestry mismatch")

    d0_policy_path = base / D0_POLICY_NAME
    d0_report_path = base / D0_REPORT_NAME
    parent = fixture["direct_design_parent"]
    if (
        file_sha256(d0_policy_path) != parent["D0_policy_sha256"]
        or file_sha256(d0_report_path) != parent["D0_report_sha256"]
        or _git_committed_bytes(base, REQUIRED_PARENT_COMMIT, D0_POLICY_NAME)
        != d0_policy_path.read_bytes()
        or _git_committed_bytes(base, REQUIRED_PARENT_COMMIT, D0_REPORT_NAME)
        != d0_report_path.read_bytes()
    ):
        raise VerificationError("P6 D0 design-parent custody mismatch")
    d0_policy = load_json(d0_policy_path)
    d0_report = load_json(d0_report_path)
    if (
        d0_policy.get("schema_version") != 1
        or d0_policy.get("policy_id") != parent["D0_policy_id"]
        or d0_policy.get("scientific_authority") != "NONE"
        or d0_policy.get("certificate_eligible") is not False
        or d0_report.get("schema_version") != 1
        or d0_report.get("report_type")
        != "majorana_p6_e768_max_lazy37_resource_report_d0_v1"
        or d0_report.get("policy_id") != parent["D0_policy_id"]
        or d0_report.get("policy_sha256") != parent["D0_policy_sha256"]
        or d0_report.get("scientific_authority") != "NONE"
        or d0_report.get("certificate_eligible") is not False
        or d0_report.get("formal_candidate_was_frozen_before_probe") != CANDIDATE_ID
        or d0_report.get("control_is_not_selectable") is not True
    ):
        raise VerificationError("P6 D0 semantic provenance mismatch")
    derived, derived_selection, derived_host = _formal_envelope_from_d0(d0_report)
    _step1, formal_step2, _cumulative, _maximum_trig = _resource_cap_sections(
        fixture, base,
    )
    if derived != formal_step2:
        raise VerificationError("P6 formal step2 caps are not frozen D0 caps")
    if derived_selection != fixture["deterministic_selection_caps"]:
        raise VerificationError("P6 formal selection caps are not frozen D0 caps")
    host = fixture["host_supervisor_caps"]
    for key, expected in derived_host.items():
        if host.get(key) != expected:
            raise VerificationError(f"P6 formal host cap differs from D0: {key}")
    if policy["D0_cap_provenance"]["D0_report_sha256"] != file_sha256(d0_report_path):
        raise VerificationError("P6 policy/D0 report custody mismatch")

    for relative in (
        P5_RESULT_CONTRACT_NAME, P5_CERTIFICATE_NAME, P5_RESULT_TEST_NAME,
    ):
        path = base / relative
        if _git_committed_bytes(base, P5_RESULT_COMMIT, relative) != path.read_bytes():
            raise VerificationError(f"P6 active P5 result drifted: {relative}")
    p5_certificate = load_json(base / P5_CERTIFICATE_NAME)
    if (
        p5_certificate.get("status") != P5.NO_CANDIDATE_STATUS
        or p5_certificate.get("selected_candidate_id") is not None
        or p5_certificate.get("result_contract_sha256")
        != file_sha256(base / P5_RESULT_CONTRACT_NAME)
    ):
        raise VerificationError("P6 required qualitative P5 parent status mismatch")
    with _p4_module_base(base):
        p4_fixture = P4.validate_fixture(load_json(base / P4_FIXTURE_NAME))
    p3_pins = p4_fixture["required_parent_P3"]
    if (
        p3_pins["direct_parent_commit"] != P3_RESULT_COMMIT
        or p3_pins["status"] != P4.PARENT_STATUS
    ):
        raise VerificationError("P6 required P3 lineage pins mismatch")
    p5_summary = {
        "result_commit_sha": P5_RESULT_COMMIT,
        "status": p5_certificate["status"],
        "selected_candidate_id": None,
    }
    p3_lineage = {
        "result_commit_sha": P3_RESULT_COMMIT,
        "status": p3_pins["status"],
        "terminal_branch": p3_pins["terminal_branch"],
        "result_contract_sha256": p3_pins["result_contract_sha256"],
        "certificate_sha256": p3_pins["certificate_sha256"],
        "canonical_witness_sha256": p3_pins["canonical_witness_sha256"],
        "accuracy_ledger_sha256": p3_pins["accuracy_ledger_sha256"],
    }
    return d0_report, p5_summary, p4_fixture, p3_lineage


def _load_p3_witness_for_uninterpreted_fieldwise_comparison(
    p4_fixture: Mapping[str, Any], base: Path = BASE,
) -> Mapping[str, Any]:
    """Load pinned P3 fields without validating or integer-decoding P3 E1."""

    base = Path(base)
    pins = p4_fixture["required_parent_P3"]
    result_path = base / P3_RESULT_CONTRACT_NAME
    result_bytes = result_path.read_bytes()
    if (
        hashlib.sha256(result_bytes).hexdigest() != pins["result_contract_sha256"]
        or _git_committed_bytes(base, P3_RESULT_COMMIT, P3_RESULT_CONTRACT_NAME)
        != result_bytes
    ):
        raise VerificationError("P6 P3 comparison witness custody mismatch")
    result = load_json(result_path)
    witness = result.get("witness")
    if not isinstance(witness, dict):
        raise SchemaError("P6 P3 comparison witness must be an object")
    if (
        result.get("canonical_witness_sha256")
        != pins["canonical_witness_sha256"]
        or canonical_sha256(witness) != pins["canonical_witness_sha256"]
        or result.get("status") != pins["status"]
        or result.get("terminal_branch") != pins["terminal_branch"]
    ):
        raise VerificationError("P6 P3 comparison witness semantic pins mismatch")
    return witness


def _status_for_terminal_branch(policy: Mapping[str, Any], branch: str) -> str:
    statuses = {
        row["branch"]: row["maximum_status"]
        for row in policy["qualification_and_terminal_truth_table"][
            "legal_terminal_branches"
        ]
    }
    if branch not in statuses:
        raise VerificationError("illegal P6 terminal branch")
    return statuses[branch]


def _authoritative_final_state(
    raw_step2_final: Mapping[str, Any], cumulative_ticks: int,
) -> dict[str, Any]:
    return P4._authoritative_final_state(raw_step2_final, cumulative_ticks)


def _compose_authoritative_witness(
    raws: Mapping[str, Mapping[str, Any]], fixture: Mapping[str, Any],
    policy: Mapping[str, Any], base: Path = BASE,
) -> dict[str, Any]:
    """After raw validation, inherit P3 E1 once and qualify the fixed candidate."""

    base = Path(base)
    if tuple(raws) != CANDIDATE_ORDER:
        raise VerificationError("P6 composed raw candidate identity mismatch")
    raw = raws[CANDIDATE_ID]
    step1, step2 = raw["step1"], raw["step2"]
    cap = step1["execution"]["cap_event"]
    projection = None
    if cap is None:
        projection = _step1_p3_projection(raw, base)
        if step2 is None:
            raise VerificationError("P6 complete step1 lacks step2")
        cap = step2["execution"]["cap_event"]

    # The cap truth is fixed before any P3 result witness is opened.  D0/P5
    # lineage below contains no P3 E1 value, and the P3 fixture exposes only
    # committed hashes/status strings.
    d0_report, p5_summary, p4_fixture, p3_lineage = (
        _verify_design_parent_and_nonnumeric_lineage(fixture, policy, base)
    )

    p3_conformance = None
    parent_inherited = False
    telescoping = None
    final_state = None
    qualified = None
    if cap is not None:
        branch = "DETERMINISTIC_POLICY_CAP_EXCEEDED"
    else:
        assert projection is not None and step2 is not None
        comparison_witness = (
            _load_p3_witness_for_uninterpreted_fieldwise_comparison(
                p4_fixture, base,
            )
        )
        try:
            _assert_fieldwise_equal(
                projection, comparison_witness,
                "P6 fresh step1 P3 conformance",
            )
        except VerificationError:
            p3_conformance = False
            branch = "FAILED_P3_POST_REPLAY_CONFORMANCE"
        else:
            p3_conformance = True
            # Only complete fieldwise equality unlocks authoritative P3 final
            # verification and semantic integer decoding of E1.
            with _p4_module_base(base):
                p3_summary, p3_result, p3_witness = P4._verify_parent_p3(
                    p4_fixture, base,
                )
            if (
                p3_summary["status"] != P4.PARENT_STATUS
                or p3_result["status"] != P4.PARENT_STATUS
            ):
                raise VerificationError("P6 required P3 authority status mismatch")
            _assert_fieldwise_equal(
                comparison_witness, p3_witness,
                "P6 pinned versus certified P3 witness",
            )
            parent_ledger = p3_witness["accuracy_ledger"]
            if parent_ledger["grid_denominator"] != str(GRID):
                raise VerificationError("P6 parent P3 defect grid mismatch")
            parent_ticks = int(parent_ledger["total_operator_error_ticks"])
            step1_ticks = int(
                raw["step1"]["accuracy_ledger"]["total_operator_error_ticks"]
            )
            if step1_ticks != parent_ticks:
                raise VerificationError("P6 fresh step1 ticks differ from P3 E1")
            if step2["final_state"] is None:
                raise VerificationError("P6 completed step2 lacks final state")
            local_ledger = step2["accuracy_ledger"]
            if local_ledger["grid_denominator"] != str(GRID):
                raise VerificationError("P6 local defect grid mismatch")
            local_ticks = int(local_ledger["total_operator_error_ticks"])
            cumulative_ticks = parent_ticks + local_ticks
            local_pass = local_ticks * 400000 < GRID
            cumulative_pass = cumulative_ticks * 200000 < GRID
            if local_pass and not cumulative_pass:
                raise VerificationError(
                    "P6 local-pass/cumulative-fail is impossible after P3 conformance"
                )
            qualified = local_pass and cumulative_pass
            if qualified:
                branch = "CANDIDATE_QUALIFIED"
            elif cumulative_pass:
                branch = "CANDIDATE_LOCAL_ALLOCATION_EXCEEDED"
            else:
                branch = "CANDIDATE_LOCAL_AND_CUMULATIVE_ALLOCATIONS_EXCEEDED"
            parent_inherited = True
            telescoping = {
                "grid_denominator": str(GRID),
                "parent_P3_operator_error_ticks": str(parent_ticks),
                "fresh_step1_recomputed_operator_error_ticks": str(step1_ticks),
                "fresh_step1_recomputation_is_conformance_not_a_second_charge": True,
                "parent_step1_error_charge_multiplicity": 1,
                "exact_unitary_parent_error_propagation_factor": 1,
                "candidate_step2_product_defect_ticks":
                    local_ledger["product_defect_ticks"],
                "candidate_step2_merge_defect_ticks":
                    local_ledger["merge_defect_ticks"],
                "candidate_step2_drop_defect_ticks":
                    local_ledger["drop_defect_ticks"],
                "candidate_step2_local_increment_ticks": str(local_ticks),
                "candidate_cumulative_two_step_operator_error_ticks":
                    str(cumulative_ticks),
                "composition_identity":
                    "parent_P3_E1_once_plus_candidate_step2_local_increment",
                "P4_or_P5_step2_error_inherited": False,
                "parent_ticks_not_requantized_rounded_or_widened_again": True,
                "candidate_step2_local_allocation": "1/400000",
                "candidate_step2_strictly_within_allocation": local_pass,
                "candidate_step2_strict_integer_comparison":
                    "candidate_local_ticks_times_400000_less_than_grid_denominator",
                "conditional_two_step_cumulative_allocation": "1/200000",
                "candidate_cumulative_strictly_within_allocation": cumulative_pass,
                "candidate_cumulative_strict_integer_comparison":
                    "candidate_cumulative_ticks_times_200000_less_than_grid_denominator",
                "candidate_qualified_iff_both_strict_comparisons": qualified,
            }
            final_state = _authoritative_final_state(
                step2["final_state"], cumulative_ticks,
            )

    candidate_result = {
        "candidate_id": CANDIDATE_ID,
        "raw_witness_sha256": canonical_sha256(raw),
        "completed_without_policy_cap": cap is None,
        "first_policy_cap_event": cap,
        "selection_resources": raw["selection_resources"],
        "independent_lazy_equals_full_domain_at_every_completed_boundary": True,
        "step1_P3_projection_sha256":
            canonical_sha256(projection) if projection is not None else None,
        "step1_P3_fieldwise_conformance": p3_conformance,
        "parent_P3_E1_inherited": parent_inherited,
        "telescoping_ledger": telescoping,
        "candidate_qualified": qualified,
        "authoritative_two_step_final_state": final_state,
    }
    status = _status_for_terminal_branch(policy, branch)
    return {
        "schema_version": 1,
        "witness_type": COMPOSED_WITNESS_TYPE,
        "fixture_id": fixture["fixture_id"],
        "fixture_sha256": file_sha256(base / FIXTURE_NAME),
        "fixture_canonical_sha256": canonical_sha256(fixture),
        "raw_witness_sha256": canonical_sha256(raw),
        "raw_witness": raw,
        "design_parent_D0": {
            "commit_sha": REQUIRED_PARENT_COMMIT,
            "policy_sha256": file_sha256(base / D0_POLICY_NAME),
            "report_sha256": file_sha256(base / D0_REPORT_NAME),
            "report_type": d0_report["report_type"],
            "scientific_authority": "NONE",
            "used_only_to_verify_pre_registered_resource_caps": True,
            "scientific_error_or_qualification_evidence_used": False,
        },
        "parent_P5_lineage": {
            **p5_summary,
            "result_contract_sha256": file_sha256(base / P5_RESULT_CONTRACT_NAME),
            "certificate_sha256": file_sha256(base / P5_CERTIFICATE_NAME),
            "numeric_error_or_final_state_inherited": False,
        },
        "parent_P3_authority": {
            **p3_lineage,
            "active_result_authority_verified_after_fieldwise_conformance":
                parent_inherited,
            "E1_charge_multiplicity": 1 if parent_inherited else 0,
        },
        "candidate_result": candidate_result,
        "both_fresh_processes_completed_before_outer_reconstruction": True,
        "candidate_qualified": qualified,
        "authoritative_two_step_final_state": final_state,
        "terminal_branch": branch,
        "status": status,
        "scope": {
            "maximum_positive_status": MAXIMUM_STATUS,
            **policy["scope_boundary"],
        },
    }


def validate_composed_witness(
    witness: Any, fixture: Mapping[str, Any], policy: Mapping[str, Any],
    runtime_lock: Mapping[str, Any], base: Path = BASE,
) -> Mapping[str, Any]:
    if not isinstance(witness, dict):
        raise SchemaError("P6 composed witness must be an object")
    require_exact_keys(
        witness,
        (
            "schema_version", "witness_type", "fixture_id", "fixture_sha256",
            "fixture_canonical_sha256", "raw_witness_sha256", "raw_witness",
            "design_parent_D0", "parent_P5_lineage", "parent_P3_authority",
            "candidate_result",
            "both_fresh_processes_completed_before_outer_reconstruction",
            "candidate_qualified", "authoritative_two_step_final_state",
            "terminal_branch", "status", "scope",
        ),
        "P6 composed witness",
    )
    raw = validate_raw_witness(
        witness["raw_witness"], fixture, runtime_lock, CANDIDATE_ID, base,
    )
    if witness["raw_witness_sha256"] != canonical_sha256(raw):
        raise VerificationError("P6 composed raw witness hash mismatch")
    expected = _compose_authoritative_witness(
        {CANDIDATE_ID: raw}, fixture, policy, base,
    )
    _assert_fieldwise_equal(witness, expected, "P6 composed witness")
    return witness


def verify_precommit(base: Path = BASE) -> dict[str, Any]:
    base = Path(base)
    fixture = validate_fixture(load_json(base / FIXTURE_NAME), base)
    runtime_lock = P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), fixture, base)
    contract = validate_precommit_contract(
        load_json(base / PRECOMMIT_CONTRACT_NAME), base,
    )
    repo, _base_relative = P2._repo_and_base_relative(base)
    resolved = P2._run_git(repo, "rev-parse", REQUIRED_PARENT_COMMIT).stdout.decode().strip()
    if resolved != REQUIRED_PARENT_COMMIT:
        raise VerificationError("P6 precommit direct design parent does not resolve")
    for artifact in contract["result_artifacts_required_absent"]:
        if (base / artifact).exists():
            raise VerificationError(f"P6 result artifact exists at precommit: {artifact}")
    return {
        "scope_ceiling": MAXIMUM_STATUS,
        "required_parent_commit": REQUIRED_PARENT_COMMIT,
        "fixture_id": fixture["fixture_id"],
        "policy_id": policy["policy_id"],
        "candidate_id": CANDIDATE_ID,
        "fresh_process_count": 2,
    }


def _outer_commit_closure(
    repo: Path, base_relative: Path, commit: str,
    contract: Mapping[str, Any], base: Path,
) -> list[dict[str, Any]]:
    pins = {row["relative_path"]: row for row in contract["source_files"]}
    rows: list[dict[str, Any]] = []
    for relative in (*PRECOMMIT_SOURCE_PATHS, PRECOMMIT_CONTRACT_NAME):
        mode, blob, body = P2._git_blob(
            repo, commit, (base_relative / relative).as_posix(),
        )
        if relative in pins:
            pin = pins[relative]
            if len(body) != pin["size_bytes"] or hashlib.sha256(body).hexdigest() != pin["sha256"]:
                raise VerificationError(f"P6 committed outer input differs from pin: {relative}")
        elif body != (Path(base) / PRECOMMIT_CONTRACT_NAME).read_bytes():
            raise VerificationError("P6 committed precommit contract differs from active bytes")
        rows.append({
            "relative_path": relative,
            "git_mode": mode,
            "git_blob": blob,
            "size_bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        })
    for relative in contract["result_artifacts_required_absent"]:
        if P2._git_path_exists(repo, commit, (base_relative / relative).as_posix()):
            raise VerificationError(f"P6 result artifact exists in precommit: {relative}")
    return rows


def _stage_runner_tree(
    repo: Path, base_relative: Path, commit: str,
    contract: Mapping[str, Any], destination: Path,
) -> list[dict[str, Any]]:
    pins = {row["relative_path"]: row for row in contract["source_files"]}
    if tuple(contract["runner_staged_files"]) != RUNNER_STAGED_PATHS:
        raise VerificationError("P6 runner staging allowlist drift")
    rows: list[dict[str, Any]] = []
    for relative in RUNNER_STAGED_PATHS:
        mode, blob, body = P2._git_blob(
            repo, commit, (base_relative / relative).as_posix(),
        )
        pin = pins[relative]
        if len(body) != pin["size_bytes"] or hashlib.sha256(body).hexdigest() != pin["sha256"]:
            raise VerificationError(f"P6 staged Git blob differs from pin: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        rows.append({
            "relative_path": relative,
            "git_mode": mode,
            "git_blob": blob,
            "size_bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        })
    forbidden_exposed = [
        relative for relative in RUNNER_FORBIDDEN_PATHS
        if (destination / relative).exists()
    ]
    if forbidden_exposed:
        raise VerificationError(
            f"P6 runner staging exposes forbidden bytes: {forbidden_exposed}"
        )
    return rows


def _run_one_isolated_replay(
    staging: Path, julia_executable: Path, depot: Path, run_root: Path,
    fixture: Mapping[str, Any], abi_mounts: Sequence[tuple[Path, str]],
    candidate_id: str,
) -> bytes:
    if candidate_id != CANDIDATE_ID:
        raise VerificationError("P6 isolated replay candidate identity drift")
    for executable in ("bwrap", "systemd-run", "systemctl"):
        if shutil.which(executable) is None:
            raise IndeterminateReplay(f"{executable} is required for P6 formal replay")
    cgroup = subprocess.run(
        ["stat", "-fc", "%T", "/sys/fs/cgroup"], capture_output=True, check=False,
    )
    if cgroup.stdout.strip() != b"cgroup2fs":
        raise IndeterminateReplay("P6 formal replay requires cgroup v2")
    scratch = run_root / "scratch"
    for relative in ("depot", "home", "tmp"):
        (scratch / relative).mkdir(parents=True, exist_ok=False)
    verified_julia = Path(julia_executable).resolve()
    runtime_root = verified_julia.parent.parent
    if verified_julia != (runtime_root / "bin" / "julia").resolve():
        raise IndeterminateReplay("P6 Julia executable differs from runtime_root/bin/julia")
    bwrap = [
        "bwrap", "--die-with-parent", "--unshare-net", "--unshare-pid",
        "--ro-bind", str(staging), "/repo",
        "--ro-bind", str(runtime_root), "/runtime",
        "--ro-bind", str(depot), "/depot-ro",
        "--bind", str(scratch), "/scratch",
        "--proc", "/proc", "--dev", "/dev",
        "--dir", "/lib64", "--dir", "/usr", "--dir", "/usr/lib",
        "--dir", "/usr/lib/x86_64-linux-gnu", "--dir", "/usr/lib/locale",
        "--dir", "/usr/lib/locale/C.utf8",
        "--dir", "/usr/lib/locale/C.utf8/LC_MESSAGES",
    ]
    for source, destination in abi_mounts:
        bwrap.extend(("--ro-bind", str(source), destination))
    bwrap.extend((
        "--clearenv", "--setenv", "HOME", "/scratch/home",
        "--setenv", "TMPDIR", "/scratch/tmp", "--setenv", "LANG", "C.UTF-8",
        "--setenv", "LC_ALL", "C.UTF-8", "--setenv", "JULIA_DEPOT_PATH",
        "/scratch/depot:/depot-ro", "--setenv", "JULIA_LOAD_PATH", "@",
        "--setenv", "JULIA_NUM_THREADS", "1", "--setenv", "OPENBLAS_NUM_THREADS", "1",
        "--setenv", "JULIA_PKG_OFFLINE", "true", "--setenv", "JULIA_PKG_SERVER", "",
        "--chdir", "/repo", "/runtime/bin/julia", "--startup-file=no",
        "--history-file=no", "--compiled-modules=no",
        "--project=/repo/majorana_certificate_p0",
        "/repo/majorana_certificate_p6/majorana_p6_runner.jl",
        "/repo/majorana_certificate_p6_fixture.json",
        "/repo/majorana_certificate_p5_fixture.json",
        "/repo/majorana_certificate_p4_fixture.json",
        "/repo/majorana_certificate_p3_fixture.json",
        "/repo/majorana_certificate_p2_fixture.json",
    ))
    host = fixture["host_supervisor_caps"]
    unit = f"majorana-p6-e768-{uuid.uuid4().hex}"
    command = [
        "systemd-run", "--user", "--scope", "--quiet", f"--unit={unit}",
        "-p", f"MemoryMax={host['MemoryMax_bytes']}",
        "-p", f"MemorySwapMax={host['MemorySwapMax_bytes']}",
        "-p", f"RuntimeMaxSec={host['RuntimeMaxSec']}", "--", *bwrap,
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None and process.stderr is not None
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    stdout_exceeded, stderr_exceeded = threading.Event(), threading.Event()
    readers = (
        threading.Thread(
            target=P2._read_limited_stream,
            args=(process.stdout, host["maximum_stdout_bytes"], stdout_chunks, stdout_exceeded),
            daemon=True,
        ),
        threading.Thread(
            target=P2._read_limited_stream,
            args=(process.stderr, host["maximum_stderr_bytes"], stderr_chunks, stderr_exceeded),
            daemon=True,
        ),
    )
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + host["outer_safety_timeout_seconds"]
    reason = None
    while process.poll() is None:
        if stdout_exceeded.is_set() or stderr_exceeded.is_set():
            reason = "stdout/stderr byte cap"
            break
        if time.monotonic() >= deadline:
            reason = "outer safety timeout"
            break
        time.sleep(0.01)
    if reason:
        P2._kill_systemd_scope(unit, process)
    try:
        returncode = process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        P2._kill_systemd_scope(unit, process)
        try:
            returncode = process.wait(timeout=10)
        except subprocess.TimeoutExpired as error:
            raise IndeterminateReplay("P6 scope termination failure") from error
    for reader in readers:
        reader.join(timeout=10)
    stdout, stderr = b"".join(stdout_chunks), b"".join(stderr_chunks)
    if reason:
        raise IndeterminateReplay(f"P6 host resource abort: {reason}")
    if stdout_exceeded.is_set() or len(stdout) > host["maximum_stdout_bytes"]:
        raise IndeterminateReplay("P6 isolated replay exceeded stdout cap")
    if stderr_exceeded.is_set() or len(stderr) > host["maximum_stderr_bytes"]:
        raise IndeterminateReplay("P6 isolated replay exceeded stderr cap")
    if returncode != 0 or stderr:
        diagnostic = stderr.decode("utf-8", errors="replace")[-4000:]
        raise IndeterminateReplay(
            f"P6 {candidate_id} isolated replay failed ({returncode}): {diagnostic}"
        )
    return stdout


def _validate_result_blind_pre_replay_inputs(
    base: Path = BASE,
) -> tuple[
    Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]
]:
    """Validate only inputs that cannot expose D0 or parent result bytes."""

    base = Path(base)
    fixture = validate_fixture(
        load_json(base / FIXTURE_NAME), base, verify_D0_custody=False,
    )
    runtime_lock = P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(
        load_json(base / POLICY_NAME), fixture, base, verify_D0_custody=False,
    )
    contract = validate_precommit_contract(
        load_json(base / PRECOMMIT_CONTRACT_NAME), base,
        verify_source_files=False, verify_D0_custody=False,
    )
    return fixture, runtime_lock, policy, contract


def fresh_replay(
    precommit_commit: str, julia_executable: Path, depot: Path,
    base: Path = BASE,
) -> dict[str, Any]:
    base = Path(base)
    fixture, runtime_lock, policy, contract = (
        _validate_result_blind_pre_replay_inputs(base)
    )
    with _p4_module_base(base):
        repo, base_relative = P2._verify_generation_git_state(
            precommit_commit, contract, base,
        )
    _verify_precommit_changed_path_allowlist(repo, base_relative, precommit_commit)
    P0._verify_julia_runtime(Path(julia_executable), runtime_lock)
    depot = Path(depot).resolve()
    depot_before = P0._verify_depot_custody(depot, runtime_lock)
    _live_mounts, abi_before = P3._host_abi_mounts_and_custody()
    p4_fixture = load_json(base / P4_FIXTURE_NAME)
    expected_environment_sha = p4_fixture["required_parent_P3"][
        "host_abi_and_locale_custody_sha256"
    ]
    if canonical_sha256(abi_before) != expected_environment_sha:
        raise IndeterminateReplay("P6 host ABI/locale differs from P3 custody")

    with tempfile.TemporaryDirectory(prefix="majorana-p6-formal-") as temporary:
        root = Path(temporary)
        environment_snapshot = root / "environment-snapshot"
        environment_snapshot.mkdir()
        abi_mounts, abi_snapshot = P3._host_abi_mounts_and_custody(
            environment_snapshot,
        )
        if abi_snapshot != abi_before:
            raise IndeterminateReplay("P6 host environment changed while taking snapshot")
        environment_snapshot_digest = P0._tree_digest(environment_snapshot)
        staging = root / "runner-staging"
        staging.mkdir()
        runner_manifest = _stage_runner_tree(
            repo, base_relative, precommit_commit, contract, staging,
        )
        staging_before = P0._tree_digest(staging)

        # Both processes finish before parsing, independent reconstruction, or
        # opening D0/P3/P4/P5 result bytes.
        outputs: list[bytes] = []
        process_bindings: list[dict[str, Any]] = []
        for ordinal in (1, 2):
            run_root = root / f"run-{ordinal}-e768"
            run_root.mkdir()
            output = _run_one_isolated_replay(
                staging, Path(julia_executable), depot, run_root, fixture,
                abi_mounts, CANDIDATE_ID,
            )
            outputs.append(output)
            process_bindings.append({
                "candidate_id": CANDIDATE_ID,
                "fresh_replay_ordinal": ordinal,
                "global_process_ordinal": ordinal,
                "stdout_sha256": hashlib.sha256(output).hexdigest(),
                "fresh_writable_scratch_and_depot_prefix": True,
                "state_cache_ranking_budget_or_checkpoint_shared": False,
            })
        if outputs[0] != outputs[1]:
            raise VerificationError("two fresh P6 stdout byte streams differ")
        # The result-blind boundary ends only after the complete raw pair is
        # present and byte-identical.  Active D0/result custody and the full
        # outer source closure are opened for the first time below.
        fixture = validate_fixture(fixture, base, verify_D0_custody=True)
        policy = validate_policy(
            policy, fixture, base, verify_D0_custody=True,
        )
        contract = validate_precommit_contract(
            load_json(base / PRECOMMIT_CONTRACT_NAME), base,
            verify_source_files=True, verify_D0_custody=True,
        )
        outer_manifest = _outer_commit_closure(
            repo, base_relative, precommit_commit, contract, base,
        )
        raw_value = _strict_persisted_json_loads(
            outputs[0], source="P6 fresh replay stdout",
            maximum_bytes=fixture["host_supervisor_caps"]["maximum_stdout_bytes"],
        )
        if outputs[0] != canonical_bytes(raw_value) + b"\n":
            raise VerificationError("P6 Julia stdout is not canonical JSON plus newline")
        raw = validate_raw_witness(
            raw_value, fixture, runtime_lock, CANDIDATE_ID, base,
        )
        composed = _compose_authoritative_witness(
            {CANDIDATE_ID: raw}, fixture, policy, base,
        )
        if P0._tree_digest(staging) != staging_before:
            raise VerificationError("P6 runner staging was modified")
        if P0._tree_digest(environment_snapshot) != environment_snapshot_digest:
            raise IndeterminateReplay("P6 captured environment changed during replay")

    if P0._verify_depot_custody(depot, runtime_lock) != depot_before:
        raise VerificationError("P6 replay modified pinned depot custody")
    _mounts_after, abi_after = P3._host_abi_mounts_and_custody()
    if abi_after != abi_before:
        raise IndeterminateReplay("P6 host environment changed during replay")
    if P2._run_git(repo, "rev-parse", "HEAD").stdout.decode().strip() != precommit_commit:
        raise VerificationError("HEAD changed during P6 replay")
    if P2._run_git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout:
        raise VerificationError("worktree changed during P6 replay")

    transcripts = [hashlib.sha256(output).hexdigest() for output in outputs]
    return {
        "schema_version": 1,
        "package_type": PACKAGE_TYPE,
        "precommit_commit_sha": precommit_commit,
        "precommit_contract_sha256": file_sha256(base / PRECOMMIT_CONTRACT_NAME),
        "outer_custody_manifest": outer_manifest,
        "outer_custody_manifest_sha256": canonical_sha256(outer_manifest),
        "runner_staging_manifest": runner_manifest,
        "runner_staging_manifest_sha256": canonical_sha256(runner_manifest),
        "runner_staging_tree_sha256": staging_before,
        "depot_custody": depot_before,
        "host_abi_and_locale_custody": abi_after,
        "host_abi_and_locale_custody_sha256": canonical_sha256(abi_after),
        "network_isolation": "bubblewrap_unshared_network_namespace",
        "PID_isolation": "bubblewrap_unshared_PID_namespace",
        "mount_isolation": (
            "eleven_file_result_blind_runner_stage_plus_runtime_read_only_depot_"
            "fresh_scratch_18_file_host_environment_and_private_proc_dev_only"
        ),
        "host_resource_enforcement": {
            "cgroup_version": 2,
            "supervisor": "systemd_user_scope",
            "MemoryMax_bytes": fixture["host_supervisor_caps"]["MemoryMax_bytes"],
            "MemorySwapMax_bytes": fixture["host_supervisor_caps"]["MemorySwapMax_bytes"],
            "RuntimeMaxSec": fixture["host_supervisor_caps"]["RuntimeMaxSec"],
            "observed_runtime_or_memory_peak_in_canonical_package": False,
        },
        "candidate_id": CANDIDATE_ID,
        "fresh_process_count": 2,
        "two_fresh_processes": True,
        "each_process_executes_step1_then_adaptive_step2_same_process": True,
        "cross_process_state_cache_checkpoint_scratch_or_ranking_state_shared": False,
        "process_bindings": process_bindings,
        "pair_stdout_byte_identical": True,
        "raw_transcript_sha256_in_order": transcripts,
        "raw_witness_sha256": canonical_sha256(raw),
        "canonical_witness_sha256": canonical_sha256(composed),
        "witness": composed,
        "terminal_branch": composed["terminal_branch"],
        "status": composed["status"],
    }


def _committed_replay_evidence(
    commit: str, contract: Mapping[str, Any], base: Path = BASE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    if (
        not isinstance(commit, str) or len(commit) != 40
        or any(character not in "0123456789abcdef" for character in commit)
    ):
        raise SchemaError("P6 precommit commit must be a full lowercase Git SHA-1")
    base = Path(base)
    repo, base_relative = P2._repo_and_base_relative(base)
    resolved = P2._run_git(repo, "rev-parse", commit).stdout.decode().strip()
    object_type = P2._run_git(repo, "cat-file", "-t", commit).stdout.decode().strip()
    if resolved != commit or object_type != "commit":
        raise VerificationError("P6 precommit commit does not resolve exactly")
    parent = P2._run_git(repo, "show", "-s", "--format=%P", commit).stdout.decode().strip()
    if parent != REQUIRED_PARENT_COMMIT:
        raise VerificationError("P6 replay commit lacks the frozen direct parent")
    _verify_precommit_changed_path_allowlist(repo, base_relative, commit)
    if P2._run_git(
        repo, "merge-base", "--is-ancestor", commit, "HEAD", check=False,
    ).returncode != 0:
        raise VerificationError("P6 replay commit is not an ancestor of current HEAD")
    remote_contains = P2._run_git(repo, "branch", "-r", "--contains", commit).stdout.decode()
    if "origin/" not in remote_contains:
        raise VerificationError("P6 replay commit was not pushed to an origin remote branch")
    outer = _outer_commit_closure(repo, base_relative, commit, contract, base)
    with tempfile.TemporaryDirectory(prefix="majorana-p6-evidence-") as temporary:
        staging = Path(temporary) / "stage"
        staging.mkdir()
        runner = _stage_runner_tree(
            repo, base_relative, commit, contract, staging,
        )
        tree_digest = P0._tree_digest(staging)
    return outer, runner, tree_digest


_PACKAGE_KEYS = (
    "schema_version", "package_type", "precommit_commit_sha",
    "precommit_contract_sha256", "outer_custody_manifest",
    "outer_custody_manifest_sha256", "runner_staging_manifest",
    "runner_staging_manifest_sha256", "runner_staging_tree_sha256",
    "depot_custody", "host_abi_and_locale_custody",
    "host_abi_and_locale_custody_sha256", "network_isolation",
    "PID_isolation", "mount_isolation", "host_resource_enforcement",
    "candidate_id", "fresh_process_count", "two_fresh_processes",
    "each_process_executes_step1_then_adaptive_step2_same_process",
    "cross_process_state_cache_checkpoint_scratch_or_ranking_state_shared",
    "process_bindings", "pair_stdout_byte_identical",
    "raw_transcript_sha256_in_order", "raw_witness_sha256",
    "canonical_witness_sha256", "witness",
    "terminal_branch", "status",
)


def _validate_replay_package(
    package: Any, base: Path = BASE,
) -> Mapping[str, Any]:
    base = Path(base)
    if not isinstance(package, dict):
        raise SchemaError("P6 replay package must be an object")
    require_exact_keys(package, _PACKAGE_KEYS, "P6 replay package")
    if package["schema_version"] != 1 or package["package_type"] != PACKAGE_TYPE:
        raise SchemaError("unexpected P6 replay package identity")
    fixture = validate_fixture(load_json(base / FIXTURE_NAME), base)
    runtime_lock = P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), fixture, base)
    precommit = validate_precommit_contract(
        load_json(base / PRECOMMIT_CONTRACT_NAME), base,
    )
    witness = validate_composed_witness(
        package["witness"], fixture, policy, runtime_lock, base,
    )
    if (
        package["terminal_branch"] != witness["terminal_branch"]
        or package["status"] != witness["status"]
    ):
        raise VerificationError("P6 replay terminal branch/status mismatch")
    if (
        package["candidate_id"] != CANDIDATE_ID
        or package["fresh_process_count"] != 2
        or package["two_fresh_processes"] is not True
        or package["each_process_executes_step1_then_adaptive_step2_same_process"]
        is not True
        or package["cross_process_state_cache_checkpoint_scratch_or_ranking_state_shared"]
        is not False
        or package["pair_stdout_byte_identical"] is not True
    ):
        raise VerificationError("P6 replay freshness/isolation evidence mismatch")
    raw = witness["raw_witness"]
    raw_bytes = canonical_bytes(raw)
    expected_raw_hash = hashlib.sha256(raw_bytes).hexdigest()
    transcript = hashlib.sha256(raw_bytes + b"\n").hexdigest()
    expected_bindings: list[dict[str, Any]] = []
    for ordinal in (1, 2):
        expected_bindings.append({
            "candidate_id": CANDIDATE_ID,
            "fresh_replay_ordinal": ordinal,
            "global_process_ordinal": ordinal,
            "stdout_sha256": transcript,
            "fresh_writable_scratch_and_depot_prefix": True,
            "state_cache_ranking_budget_or_checkpoint_shared": False,
        })
    if package["raw_witness_sha256"] != expected_raw_hash:
        raise VerificationError("P6 raw witness digest mismatch")
    if package["raw_transcript_sha256_in_order"] != [transcript, transcript]:
        raise VerificationError("P6 raw transcript digest list mismatch")
    if package["process_bindings"] != expected_bindings:
        raise VerificationError("P6 process/ordinal binding mismatch")
    if package["canonical_witness_sha256"] != canonical_sha256(witness):
        raise VerificationError("P6 composed witness digest mismatch")
    if package["precommit_contract_sha256"] != file_sha256(base / PRECOMMIT_CONTRACT_NAME):
        raise VerificationError("P6 replay precommit contract digest mismatch")
    if (
        package["network_isolation"] != "bubblewrap_unshared_network_namespace"
        or package["PID_isolation"] != "bubblewrap_unshared_PID_namespace"
        or package["mount_isolation"] != (
            "eleven_file_result_blind_runner_stage_plus_runtime_read_only_depot_"
            "fresh_scratch_18_file_host_environment_and_private_proc_dev_only"
        )
    ):
        raise VerificationError("P6 replay isolation declaration mismatch")
    expected_host = {
        "cgroup_version": 2,
        "supervisor": "systemd_user_scope",
        "MemoryMax_bytes": fixture["host_supervisor_caps"]["MemoryMax_bytes"],
        "MemorySwapMax_bytes": fixture["host_supervisor_caps"]["MemorySwapMax_bytes"],
        "RuntimeMaxSec": fixture["host_supervisor_caps"]["RuntimeMaxSec"],
        "observed_runtime_or_memory_peak_in_canonical_package": False,
    }
    if package["host_resource_enforcement"] != expected_host:
        raise VerificationError("P6 replay host resource declaration mismatch")
    environment = P3._validate_environment_manifest(
        package["host_abi_and_locale_custody"]
    )
    p4_fixture = load_json(base / P4_FIXTURE_NAME)
    if (
        package["host_abi_and_locale_custody_sha256"] != canonical_sha256(environment)
        or package["host_abi_and_locale_custody_sha256"]
        != p4_fixture["required_parent_P3"]["host_abi_and_locale_custody_sha256"]
    ):
        raise VerificationError("P6 replay environment custody mismatch")
    P2._validate_recorded_depot_custody(package["depot_custody"], runtime_lock)
    outer, runner, tree_digest = _committed_replay_evidence(
        package["precommit_commit_sha"], precommit, base,
    )
    if (
        package["outer_custody_manifest"] != outer
        or package["outer_custody_manifest_sha256"] != canonical_sha256(outer)
    ):
        raise VerificationError("P6 outer custody evidence mismatch")
    if (
        package["runner_staging_manifest"] != runner
        or package["runner_staging_manifest_sha256"] != canonical_sha256(runner)
        or package["runner_staging_tree_sha256"] != tree_digest
    ):
        raise VerificationError("P6 runner staging evidence mismatch")
    for field in (
        "precommit_contract_sha256", "outer_custody_manifest_sha256",
        "runner_staging_manifest_sha256", "runner_staging_tree_sha256",
        "host_abi_and_locale_custody_sha256", "canonical_witness_sha256",
    ):
        require_sha256(package[field], f"P6 replay {field}")
    require_sha256(package["raw_witness_sha256"], "P6 raw witness hash")
    return package


CUSTODY_CERTIFICATE_CLAIMS = (
    "fixed_L8_E768_MAX_LAZY37_V1_candidate_started_from_O0",
    "two_fresh_network_and_PID_isolated_cgroup_limited_processes",
    "byte_identical_canonical_stdout_across_the_fresh_pair",
    "eleven_file_result_blind_runner_stage_and_host_environment_custody",
    "D0_used_only_for_pre_registered_resource_caps_without_scientific_authority",
)

COMPLETED_REPLAY_CLAIMS = (
    "fixed_L8_P3_2^-34_step1_then_fixed_E768_MAX_LAZY37_V1_step2_execution",
    "independent_integer_binary64_RNE_replay_through_the_fixed_two_step_prefix",
    "full_domain_bruteforce_and_lazy_membership_equivalence_at_every_completed_boundary",
    "ordered_ComplexF64_times_Complex_Int64_signed_zero_regression_guard",
)

COMMON_CERTIFICATE_CLAIMS = (
    *CUSTODY_CERTIFICATE_CLAIMS,
    *COMPLETED_REPLAY_CLAIMS,
)

COMPLETED_CANDIDATE_CLAIMS = (
    "complete_fieldwise_conformance_of_fresh_step1_to_certified_P3",
    "P3_E1_inherited_exactly_once_after_conformance",
    "P4_and_P5_step2_numeric_error_final_state_and_terminal_result_not_inherited",
    "E768_step2_product_merge_and_executed_drop_local_defect_ledgers",
    "strict_E768_local_one_over_400000_comparison",
    "strict_conditional_two_step_cumulative_one_over_200000_comparison",
    "exact_dyadic_E768_Neel_center_and_conditional_two_step_interval",
)

QUALIFIED_CANDIDATE_CLAIMS = (
    "fixed_E768_candidate_passes_both_strict_allocations",
    "fixed_E768_two_step_operator_and_checkerboard_Neel_enclosure_certified",
)

LOCAL_NEGATIVE_CLAIMS = (
    "fixed_E768_candidate_exceeds_the_strict_local_allocation",
    "fixed_E768_candidate_remains_within_the_strict_cumulative_allocation",
    "negative_authority_is_limited_to_this_fixed_candidate",
)

BOTH_NEGATIVE_CLAIMS = (
    "fixed_E768_candidate_exceeds_both_strict_allocations",
    "negative_authority_is_limited_to_this_fixed_candidate",
)

CAP_ONLY_CLAIMS = (
    "fresh_pair_reproduces_the_same_first_deterministic_policy_cap",
    "policy_cap_has_resource_guard_authority_only",
    "no_completed_allocation_or_candidate_qualification_claim",
    "P3_E1_not_inherited_on_the_cap_only_branch",
)

FAILED_CONFORMANCE_CLAIMS = (
    "complete_fresh_step1_projection_failed_certified_P3_fieldwise_conformance",
    "P3_E1_not_decoded_or_inherited_after_conformance_failure",
    "failure_branch_has_no_scientific_bound_authority",
)

# Public maximum-positive vocabulary; materialization narrows it for every
# non-positive terminal branch.
CERTIFICATE_CLAIMS = (
    *COMMON_CERTIFICATE_CLAIMS,
    *COMPLETED_CANDIDATE_CLAIMS,
    *QUALIFIED_CANDIDATE_CLAIMS,
)

CERTIFICATE_EXCLUSIONS = (
    "uniform_or_alternative_thresholds_across_either_step",
    "global_optimality_of_the_causal_prefix_adaptive_algorithm",
    "global_coefficientwise_interval_state",
    "equality_of_executed_and_exact_arithmetic_drop_sets",
    "raw_unfused_constituent_threshold_path",
    "cancellation_correlation_future_budget_or_cross_candidate_error_credit",
    "general_adaptive_drop_method_or_actual_simulation_error_no_go",
    "double_occupancy",
    "remaining_98_mapped_steps_or_full_R100",
    "product_formula_to_exact_Hubbard_error_or_exact_time_evolution",
    "arbitrary_lattice_initial_state_or_observable",
    "physical_reference_qualification_or_READY",
    "D0_resource_observations_as_scientific_error_or_qualification_evidence",
    "host_runtime_RSS_paths_timestamps_inodes_or_process_identifiers",
)


_RESULT_KEYS = (
    "schema_version", "contract_type", "precommit_commit_sha",
    "precommit_contract_sha256", "replay_package_sha256",
    "outer_custody_manifest_sha256", "runner_staging_manifest_sha256",
    "runner_staging_tree_sha256", "depot_custody",
    "host_abi_and_locale_custody", "host_abi_and_locale_custody_sha256",
    "network_isolation", "PID_isolation", "mount_isolation",
    "host_resource_enforcement", "candidate_id", "fresh_process_count",
    "two_fresh_processes",
    "each_process_executes_step1_then_adaptive_step2_same_process",
    "cross_process_state_cache_checkpoint_scratch_or_ranking_state_shared",
    "process_bindings", "pair_stdout_byte_identical",
    "raw_transcript_sha256_in_order", "raw_witness_sha256",
    "canonical_witness_sha256", "witness", "terminal_branch", "status",
    "scope",
)


def _certificate_authority_and_claims(
    package: Mapping[str, Any],
) -> tuple[str, list[str]]:
    branch = package["terminal_branch"]
    witness = package["witness"]
    qualified = witness["candidate_qualified"]
    candidate_result = witness["candidate_result"]
    telescoping = candidate_result["telescoping_ledger"]
    if branch == "CANDIDATE_QUALIFIED":
        if qualified is not True or telescoping is None:
            raise VerificationError("P6 qualified branch lacks positive evidence")
        if (
            telescoping["candidate_step2_strictly_within_allocation"] is not True
            or telescoping["candidate_cumulative_strictly_within_allocation"]
            is not True
        ):
            raise VerificationError("P6 qualified branch allocation bits mismatch")
        return (
            "fixed_L8_P3_2^-34_step1_then_E768_MAX_LAZY37_V1_step2_two_step_operator_and_checkerboard_Neel_enclosure_only",
            list(CERTIFICATE_CLAIMS),
        )
    if branch == "CANDIDATE_LOCAL_ALLOCATION_EXCEEDED":
        if qualified is not False or telescoping is None:
            raise VerificationError("P6 local-negative branch lacks completed evidence")
        if (
            telescoping["candidate_step2_strictly_within_allocation"] is not False
            or telescoping["candidate_cumulative_strictly_within_allocation"]
            is not True
        ):
            raise VerificationError("P6 local-negative allocation bits mismatch")
        return (
            "completed_fixed_E768_candidate_local_allocation_failure_only_not_a_general_adaptive_drop_or_simulation_no_go",
            [
                *COMMON_CERTIFICATE_CLAIMS,
                *COMPLETED_CANDIDATE_CLAIMS,
                *LOCAL_NEGATIVE_CLAIMS,
            ],
        )
    if branch == "CANDIDATE_LOCAL_AND_CUMULATIVE_ALLOCATIONS_EXCEEDED":
        if qualified is not False or telescoping is None:
            raise VerificationError("P6 dual-negative branch lacks completed evidence")
        if (
            telescoping["candidate_step2_strictly_within_allocation"] is not False
            or telescoping["candidate_cumulative_strictly_within_allocation"]
            is not False
        ):
            raise VerificationError("P6 dual-negative allocation bits mismatch")
        return (
            "completed_fixed_E768_candidate_local_and_cumulative_allocation_failure_only_not_a_general_adaptive_drop_or_simulation_no_go",
            [
                *COMMON_CERTIFICATE_CLAIMS,
                *COMPLETED_CANDIDATE_CLAIMS,
                *BOTH_NEGATIVE_CLAIMS,
            ],
        )
    if branch == "DETERMINISTIC_POLICY_CAP_EXCEEDED":
        if qualified is not None or candidate_result["first_policy_cap_event"] is None:
            raise VerificationError("P6 cap branch lacks its resource event")
        return (
            "resource_guard_event_only_without_E1_inheritance_allocation_assessment_or_candidate_accept_reject_authority",
            [*CUSTODY_CERTIFICATE_CLAIMS, *CAP_ONLY_CLAIMS],
        )
    if branch == "FAILED_P3_POST_REPLAY_CONFORMANCE":
        if (
            qualified is not None
            or candidate_result["step1_P3_fieldwise_conformance"] is not False
        ):
            raise VerificationError("P6 conformance-failure evidence mismatch")
        return (
            "none_and_P3_E1_must_not_be_decoded_or_inherited",
            [*COMMON_CERTIFICATE_CLAIMS, *FAILED_CONFORMANCE_CLAIMS],
        )
    raise VerificationError("P6 terminal branch cannot materialize a certificate")


def materialize_result(
    replay_package: Mapping[str, Any], base: Path = BASE,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = Path(base)
    package = _validate_replay_package(replay_package, base)
    certificate_authority, certificate_claims = _certificate_authority_and_claims(
        package
    )
    contract = {
        "schema_version": 1,
        "contract_type": RESULT_CONTRACT_TYPE,
        "precommit_commit_sha": package["precommit_commit_sha"],
        "precommit_contract_sha256": package["precommit_contract_sha256"],
        "replay_package_sha256": hashlib.sha256(
            canonical_bytes(package) + b"\n"
        ).hexdigest(),
        "outer_custody_manifest_sha256": package["outer_custody_manifest_sha256"],
        "runner_staging_manifest_sha256": package["runner_staging_manifest_sha256"],
        "runner_staging_tree_sha256": package["runner_staging_tree_sha256"],
        "depot_custody": package["depot_custody"],
        "host_abi_and_locale_custody": package["host_abi_and_locale_custody"],
        "host_abi_and_locale_custody_sha256": package[
            "host_abi_and_locale_custody_sha256"
        ],
        "network_isolation": package["network_isolation"],
        "PID_isolation": package["PID_isolation"],
        "mount_isolation": package["mount_isolation"],
        "host_resource_enforcement": package["host_resource_enforcement"],
        "candidate_id": package["candidate_id"],
        "fresh_process_count": package["fresh_process_count"],
        "two_fresh_processes": package["two_fresh_processes"],
        "each_process_executes_step1_then_adaptive_step2_same_process": package[
            "each_process_executes_step1_then_adaptive_step2_same_process"
        ],
        "cross_process_state_cache_checkpoint_scratch_or_ranking_state_shared": package[
            "cross_process_state_cache_checkpoint_scratch_or_ranking_state_shared"
        ],
        "process_bindings": package["process_bindings"],
        "pair_stdout_byte_identical": package["pair_stdout_byte_identical"],
        "raw_transcript_sha256_in_order": package[
            "raw_transcript_sha256_in_order"
        ],
        "raw_witness_sha256": package["raw_witness_sha256"],
        "canonical_witness_sha256": package["canonical_witness_sha256"],
        "witness": package["witness"],
        "terminal_branch": package["terminal_branch"],
        "status": package["status"],
        "scope": package["witness"]["scope"],
    }
    certificate = {
        "schema_version": 1,
        "certificate_type": CERTIFICATE_TYPE,
        "status": package["status"],
        "terminal_branch": package["terminal_branch"],
        "authority": certificate_authority,
        "candidate_id": package["candidate_id"],
        "candidate_qualified": package["witness"]["candidate_qualified"],
        "result_contract_sha256": hashlib.sha256(
            canonical_bytes(contract) + b"\n"
        ).hexdigest(),
        "precommit_commit_sha": package["precommit_commit_sha"],
        "policy_sha256": file_sha256(base / POLICY_NAME),
        "runtime_lock_sha256": file_sha256(base / RUNTIME_LOCK_NAME),
        "fixture_sha256": file_sha256(base / FIXTURE_NAME),
        "runner_sha256": file_sha256(base / RUNNER_RELATIVE_PATH),
        "checker_sha256": file_sha256(base / CHECKER_NAME),
        "design_parent_D0_policy_sha256": file_sha256(base / D0_POLICY_NAME),
        "design_parent_D0_report_sha256": file_sha256(base / D0_REPORT_NAME),
        "D0_has_scientific_or_qualification_authority": False,
        "parent_P5_result_contract_sha256": file_sha256(
            base / P5_RESULT_CONTRACT_NAME
        ),
        "parent_P5_certificate_sha256": file_sha256(base / P5_CERTIFICATE_NAME),
        "P4_or_P5_numeric_E12_step2_error_final_state_or_terminal_result_inherited":
            False,
        "parent_P3_result_contract_sha256": file_sha256(
            base / P3_RESULT_CONTRACT_NAME
        ),
        "parent_P3_certificate_sha256": file_sha256(base / P3_CERTIFICATE_NAME),
        "raw_witness_sha256": package["raw_witness_sha256"],
        "canonical_witness_sha256": package["canonical_witness_sha256"],
        "candidate_result_sha256": canonical_sha256(
            package["witness"]["candidate_result"]
        ),
        "claims": certificate_claims,
        "explicit_exclusions": list(CERTIFICATE_EXCLUSIONS),
        "ready_gate_eligible": False,
    }
    return contract, certificate


def _package_from_result(
    result: Mapping[str, Any], precommit: Mapping[str, Any], base: Path,
) -> dict[str, Any]:
    outer, runner, tree_digest = _committed_replay_evidence(
        result["precommit_commit_sha"], precommit, base,
    )
    if result["outer_custody_manifest_sha256"] != canonical_sha256(outer):
        raise VerificationError("P6 result outer custody digest mismatch")
    if result["runner_staging_manifest_sha256"] != canonical_sha256(runner):
        raise VerificationError("P6 result runner staging digest mismatch")
    if result["runner_staging_tree_sha256"] != tree_digest:
        raise VerificationError("P6 result runner staging tree digest mismatch")
    return {
        "schema_version": 1,
        "package_type": PACKAGE_TYPE,
        "precommit_commit_sha": result["precommit_commit_sha"],
        "precommit_contract_sha256": result["precommit_contract_sha256"],
        "outer_custody_manifest": outer,
        "outer_custody_manifest_sha256": result["outer_custody_manifest_sha256"],
        "runner_staging_manifest": runner,
        "runner_staging_manifest_sha256": result["runner_staging_manifest_sha256"],
        "runner_staging_tree_sha256": result["runner_staging_tree_sha256"],
        "depot_custody": result["depot_custody"],
        "host_abi_and_locale_custody": result["host_abi_and_locale_custody"],
        "host_abi_and_locale_custody_sha256": result[
            "host_abi_and_locale_custody_sha256"
        ],
        "network_isolation": result["network_isolation"],
        "PID_isolation": result["PID_isolation"],
        "mount_isolation": result["mount_isolation"],
        "host_resource_enforcement": result["host_resource_enforcement"],
        "candidate_id": result["candidate_id"],
        "fresh_process_count": result["fresh_process_count"],
        "two_fresh_processes": result["two_fresh_processes"],
        "each_process_executes_step1_then_adaptive_step2_same_process": result[
            "each_process_executes_step1_then_adaptive_step2_same_process"
        ],
        "cross_process_state_cache_checkpoint_scratch_or_ranking_state_shared": result[
            "cross_process_state_cache_checkpoint_scratch_or_ranking_state_shared"
        ],
        "process_bindings": result["process_bindings"],
        "pair_stdout_byte_identical": result["pair_stdout_byte_identical"],
        "raw_transcript_sha256_in_order": result[
            "raw_transcript_sha256_in_order"
        ],
        "raw_witness_sha256": result["raw_witness_sha256"],
        "canonical_witness_sha256": result["canonical_witness_sha256"],
        "witness": result["witness"],
        "terminal_branch": result["terminal_branch"],
        "status": result["status"],
    }


def verify_final(base: Path = BASE) -> dict[str, Any]:
    base = Path(base)
    fixture = validate_fixture(load_json(base / FIXTURE_NAME), base)
    P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), fixture, base)
    precommit = validate_precommit_contract(
        load_json(base / PRECOMMIT_CONTRACT_NAME), base,
    )
    result_path = base / RESULT_CONTRACT_NAME
    certificate_path = base / CERTIFICATE_NAME
    result = _load_persisted_json(result_path, base)
    certificate = _load_persisted_json(certificate_path, base)
    if not isinstance(result, dict):
        raise SchemaError("P6 result contract must be an object")
    require_exact_keys(result, _RESULT_KEYS, "P6 result contract")
    if result["schema_version"] != 1 or result["contract_type"] != RESULT_CONTRACT_TYPE:
        raise SchemaError("unexpected P6 result contract identity")
    if result_path.read_bytes() != canonical_bytes(result) + b"\n":
        raise VerificationError("P6 result contract is not canonical JSON plus newline")
    package = _package_from_result(result, precommit, base)
    _validate_replay_package(package, base)
    if result["replay_package_sha256"] != hashlib.sha256(
        canonical_bytes(package) + b"\n"
    ).hexdigest():
        raise VerificationError("P6 replay package digest is not reconstructible")
    if result["scope"] != result["witness"]["scope"]:
        raise VerificationError("P6 result scope mismatch")
    expected_contract, expected_certificate = materialize_result(package, base)
    if result != expected_contract:
        raise VerificationError("P6 result contract content mismatch")
    if certificate_path.read_bytes() != canonical_bytes(certificate) + b"\n":
        raise VerificationError("P6 certificate is not canonical JSON plus newline")
    if certificate != expected_certificate:
        raise VerificationError("P6 certificate content mismatch")
    return {
        "status": result["status"],
        "terminal_branch": result["terminal_branch"],
        "candidate_id": result["candidate_id"],
        "candidate_qualified": result["witness"]["candidate_qualified"],
        "precommit_commit_sha": result["precommit_commit_sha"],
        "raw_witness_sha256": result["raw_witness_sha256"],
        "canonical_witness_sha256": result["canonical_witness_sha256"],
        "result_contract_sha256": file_sha256(result_path),
        "certificate_sha256": file_sha256(certificate_path),
        "policy_id": policy["policy_id"],
    }


def _write_canonical_json(path: Path, value: Any) -> None:
    path = Path(path)
    payload = canonical_bytes(value) + b"\n"
    temporary = path.with_name(path.name + f".tmp-{uuid.uuid4().hex}")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-precommit", action="store_true")
    parser.add_argument("--fresh-replay", action="store_true")
    parser.add_argument("--materialize-result", action="store_true")
    parser.add_argument("--verify-final", action="store_true")
    parser.add_argument("--precommit-commit")
    parser.add_argument("--julia", type=Path)
    parser.add_argument("--depot", type=Path)
    parser.add_argument("--replay-output", type=Path)
    parser.add_argument("--contract-output", type=Path)
    parser.add_argument("--certificate-output", type=Path)
    args = parser.parse_args(argv)
    selected = sum(map(int, (
        args.verify_precommit, args.fresh_replay, args.materialize_result,
        args.verify_final,
    )))
    if selected != 1:
        parser.error("select exactly one operation")
    if args.verify_precommit:
        summary = verify_precommit()
    elif args.fresh_replay:
        if not all((args.precommit_commit, args.julia, args.depot, args.replay_output)):
            parser.error("fresh replay requires commit, Julia, depot, and replay output")
        try:
            package = fresh_replay(
                args.precommit_commit, args.julia, args.depot,
            )
        except IndeterminateReplay as error:
            print(json.dumps(
                {"status": "INDETERMINATE", "reason": str(error)},
                sort_keys=True, separators=(",", ":"),
            ))
            return 2
        _write_canonical_json(args.replay_output, package)
        summary = {
            "status": package["status"],
            "terminal_branch": package["terminal_branch"],
            "candidate_id": package["candidate_id"],
            "candidate_qualified": package["witness"]["candidate_qualified"],
            "raw_witness_sha256": package["raw_witness_sha256"],
            "canonical_witness_sha256": package["canonical_witness_sha256"],
            "raw_transcript_sha256_in_order": package[
                "raw_transcript_sha256_in_order"
            ],
        }
    elif args.materialize_result:
        if not all((args.replay_output, args.contract_output, args.certificate_output)):
            parser.error("materialization requires replay, contract, and certificate paths")
        package = _strict_persisted_json_loads(
            args.replay_output.read_bytes(), source="P6 replay package",
            maximum_bytes=_persisted_result_byte_cap(BASE),
        )
        contract, certificate = materialize_result(package)
        _write_canonical_json(args.contract_output, contract)
        _write_canonical_json(args.certificate_output, certificate)
        summary = {
            "status": contract["status"],
            "terminal_branch": contract["terminal_branch"],
            "candidate_id": contract["candidate_id"],
            "candidate_qualified": contract["witness"]["candidate_qualified"],
            "result_contract_sha256": file_sha256(args.contract_output),
            "certificate_sha256": file_sha256(args.certificate_output),
        }
    else:
        summary = verify_final()
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
