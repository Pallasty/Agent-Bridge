#!/usr/bin/env python3
"""Independent checker for the Majorana P5 conditional-threshold campaign.

P5 deliberately changes only the second mapped step.  Every formal candidate
therefore starts from O0, freshly executes the certified P3 step-one path with
the strict 2^-34 threshold, and then executes step two in the same Julia
process with its pre-registered 2^-36 or 2^-37 threshold.  Two fresh processes
are required for each candidate and each pair of stdout byte streams must be
identical.

The Julia runners are result blind.  This checker validates all four raw
processes before it opens the D0 report or any P3/P4 result artifact.  It then
checks the fresh step-one projection field by field, inherits P3's E1 exactly
once per candidate, and applies the pre-registered least-aggressive selector
only if both candidates completed.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from fractions import Fraction
import hashlib
import importlib.util
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
FIXTURE_NAME = "majorana_certificate_p5_fixture.json"
POLICY_NAME = "majorana_certificate_p5_policy.json"
PRECOMMIT_CONTRACT_NAME = "majorana_certificate_p5_precommit_contract.json"
RESULT_CONTRACT_NAME = "majorana_certificate_p5_contract.json"
CERTIFICATE_NAME = "majorana_certificate_p5_certificate.json"
RESULT_TEST_NAME = "test_majorana_certificate_p5_result.py"
PRECOMMIT_TEST_NAME = "test_majorana_certificate_p5.py"
CHECKER_NAME = "majorana_certificate_p5_checker.py"
RUNNER_RELATIVE_PATH = "majorana_certificate_p5/majorana_p5_runner.jl"

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
D0_POLICY_NAME = "majorana_certificate_p5_design_probe_policy.json"
D0_REPORT_NAME = "majorana_certificate_p5_design_probe_report.json"
D0_CHECKER_NAME = "majorana_certificate_p5_design_probe.py"
D0_PRECOMMIT_TEST_NAME = "test_majorana_certificate_p5_design_probe.py"
D0_RESULT_TEST_NAME = "test_majorana_certificate_p5_design_probe_result.py"
D0_RUNNER_RELATIVE_PATH = (
    "majorana_certificate_p5_design_probe/majorana_p5_threshold_resource_probe.jl"
)

REQUIRED_PARENT_COMMIT = "0265c7a4d726bf5b875247d0412e6a1d2f909973"
P4_RESULT_COMMIT = "b0028fbd9ac079a64406bc2808ef7943045887a3"
P3_RESULT_COMMIT = "d5b63abe941ff0a723dd7c15a61b9ab8298286ab"

FIXTURE_ID = "MAJORANA-P5-L8-CONDITIONAL-STEP2-THRESHOLD-S0-V1"
FIXTURE_CANONICAL_SHA256 = (
    "bbac5a9281198ba87b336c6e45741d1468f85bb2997317943f1a45b6ac90de91"
)
POLICY_CANONICAL_SHA256 = (
    "6fdce5556d5e226ece5b51608a1632bbc9120347ee4fbd9d757cba118862b4ff"
)
RAW_WITNESS_TYPE = (
    "majorana_p5_L8_conditional_step2_threshold_candidate_execution_raw_v1"
)
COMPOSED_WITNESS_TYPE = (
    "majorana_p5_L8_conditional_step2_threshold_comparison_authoritative_witness_v1"
)
PACKAGE_TYPE = "majorana_p5_formal_fresh_conditional_threshold_replay_package_v1"
PRECOMMIT_CONTRACT_TYPE = (
    "majorana_p5_result_unpinned_conditional_step2_threshold_"
    "comparison_input_and_isolation_contract_v1"
)
RESULT_CONTRACT_TYPE = "majorana_p5_formal_conditional_threshold_result_contract_v1"
CERTIFICATE_TYPE = (
    "majorana_p5_conditional_step2_threshold_comparison_bound_subcertificate_v1"
)

K36_SELECTED_STATUS = (
    "VERIFIED_MAJORANA_P5_L8_CONDITIONAL_STEP2_K36_SELECTED_LOCAL_AND_"
    "CUMULATIVE_ERROR_BOUNDS_WITHIN_ALLOCATIONS_SUBCERTIFICATE"
)
K37_SELECTED_STATUS = (
    "VERIFIED_MAJORANA_P5_L8_CONDITIONAL_STEP2_K37_SELECTED_LOCAL_AND_"
    "CUMULATIVE_ERROR_BOUNDS_WITHIN_ALLOCATIONS_SUBCERTIFICATE"
)
NO_CANDIDATE_STATUS = (
    "VERIFIED_MAJORANA_P5_L8_CONDITIONAL_STEP2_K36_K37_ERROR_BOUNDS_"
    "NO_SELECTION_SUBCERTIFICATE"
)
CAP_STATUS = (
    "VERIFIED_MAJORANA_P5_L8_REQUIRED_THRESHOLD_CANDIDATE_POLICY_CAP_"
    "EXCEEDED_SUBCERTIFICATE"
)
FAILED_CONFORMANCE_STATUS = "FAILED_MAJORANA_P5_STEP1_P3_POST_REPLAY_CONFORMANCE"
INDETERMINATE_STATUS = "INDETERMINATE_MAJORANA_P5_REPLAY"
INVALID_STATUS = "INVALID_MAJORANA_P5_REPLAY"
MAXIMUM_STATUS = K36_SELECTED_STATUS

STEP2_ALLOCATION = Fraction(1, 400000)
CUMULATIVE_ALLOCATION = Fraction(1, 200000)
STEP1_THRESHOLD_BITS = 0x3DD0000000000000
CANDIDATE_BITS = {"K36": 0x3DB0000000000000, "K37": 0x3DA0000000000000}
CANDIDATE_EXPONENTS = {"K36": 36, "K37": 37}
CANDIDATE_ORDER = ("K36", "K37")


def _load_helper(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P4 = _load_helper("majorana_p5_p4_helper", BASE / P4_CHECKER_NAME)
P3 = P4.P3
P2 = P4.P2
P0 = P4.P0
SchemaError = P4.SchemaError
VerificationError = P4.VerificationError
IndeterminateReplay = P4.IndeterminateReplay
canonical_bytes = P4.canonical_bytes
canonical_sha256 = P4.canonical_sha256
file_sha256 = P4.file_sha256
require_exact_keys = P4.require_exact_keys
require_sha256 = P4.require_sha256
GRID = P4.GRID
GRID_BITS = P4.GRID_BITS
SIGN_MASK = P4.SIGN_MASK
REPLAY_ENVIRONMENT_TARGETS = P4.REPLAY_ENVIRONMENT_TARGETS


def _persisted_result_byte_cap(base: Path = BASE) -> int:
    """Bound P5 replay/result containers without relaxing Julia stdout."""

    fixture = load_json(Path(base) / FIXTURE_NAME)
    host = fixture.get("host_supervisor_caps")
    if not isinstance(host, dict):
        raise SchemaError("P5 fixture lacks host supervisor caps")
    per_process = host.get("maximum_stdout_bytes")
    if type(per_process) is not int or per_process <= 0:
        raise SchemaError("P5 fixture has an invalid stdout byte cap")
    # A persisted comparison container may carry evidence derived from all four
    # frozen fresh processes.  This cap is therefore derived only from the
    # result-blind process count and the already frozen per-process stdout cap.
    return 4 * per_process


def _strict_persisted_json_loads(
    data: bytes, *, source: str, maximum_bytes: int,
) -> Any:
    """Strict JSON parser for P5 containers that may exceed the P3 stdout cap."""

    if len(data) > maximum_bytes:
        raise SchemaError("P5 persisted JSON exceeds its derived byte cap")

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
        if value.bit_length() > P3.MAX_JSON_INTEGER_BITS:
            raise SchemaError("JSON integer exceeds the P3 bit cap")
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
    D0_POLICY_NAME,
    D0_REPORT_NAME,
    RESULT_CONTRACT_NAME,
    CERTIFICATE_NAME,
    RESULT_TEST_NAME,
)

# This is the outer checker's custody closure, not the runner stage.  It may
# contain the result-bearing P3/P4 and non-authoritative D0 artifacts, but those
# rows are opened only after all four raw processes finish in ``fresh_replay``.
PRECOMMIT_SOURCE_PATHS = tuple(sorted(set(P4.PRECOMMIT_SOURCE_PATHS) | {
    P4_PRECOMMIT_CONTRACT_NAME,
    P4_RESULT_CONTRACT_NAME,
    P4_CERTIFICATE_NAME,
    P4_RESULT_TEST_NAME,
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
# only these six P5 S0 files.  This closes the Git tree against renamed raw
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
    "conditional_step2_local_defect_and_Neel_enclosure": "ASSESSED",
    "candidate_cumulative_allocation_or_selection": "OUTER_CHECKER_ONLY",
    "global_two_step_or_coefficientwise_interval_state": "NOT_CLAIMED_BY_RUNNER",
    "exact_arithmetic_threshold_drop_set": "NOT_CLAIMED_EQUAL",
    "budget_constrained_drop": "NOT_ASSESSED",
    "remaining_98_mapped_steps_or_full_R100": "NOT_ASSESSED",
    "product_formula_to_exact_Hubbard_error_or_exact_time_evolution": "NOT_ASSESSED",
    "double_occupancy": "NOT_ASSESSED",
    "arbitrary_initial_state_or_lattice_size": "NOT_CLAIMED",
    "P3_or_P4_result_available_to_runner": False,
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


def _expected_candidate_rows() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "K36",
            "fresh_process_count": 2,
            "strict_less_than": True,
            "threshold_Float64_bits_hex": "3db0000000000000",
            "threshold_exponent": 36,
            "threshold_rational": "1/68719476736",
        },
        {
            "candidate_id": "K37",
            "fresh_process_count": 2,
            "strict_less_than": True,
            "threshold_Float64_bits_hex": "3da0000000000000",
            "threshold_exponent": 37,
            "threshold_rational": "1/137438953472",
        },
    ]


_EXPECTED_STEP2_CAPS = {
    "maximum_current_terms_before_constituent": 524288,
    "maximum_premerge_terms": 524288,
    "maximum_boundary_retained_terms": 524288,
    "maximum_cap_scan_term_visits": 536870912,
    "maximum_propagation_term_visits": 536870912,
    "maximum_truncation_term_visits": 268435456,
    "maximum_final_evaluation_term_visits": 524288,
    "maximum_total_charged_term_visits": 1073741824,
    "maximum_anticommuting_events": 16777216,
    "maximum_product_defect_events": 33554432,
    "maximum_merge_defect_events": 4194304,
    "maximum_drop_defect_events": 8388608,
    "maximum_accuracy_charged_events": 33554432,
    "maximum_total_P2_plus_accuracy_charged_events": 1073741824,
    "maximum_composites": 512,
    "maximum_constituents": 1152,
    "maximum_truncation_boundaries": 768,
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
    P4._validate_cap_map(p4_step1, _STEP_CAP_KEYS, "P5 normalized step1 caps")
    P4._validate_cap_map(step2, _STEP_CAP_KEYS, "P5 normalized step2 caps")
    if step2 != _EXPECTED_STEP2_CAPS:
        raise VerificationError("P5 formal step2 caps differ from the frozen D0 derivation")
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
    P4._validate_cap_map(cumulative, _CUMULATIVE_CAP_KEYS, "P5 cumulative caps")
    maximum_trig = _positive_int(
        root["maximum_trig_table_entries"], "P5 maximum_trig_table_entries",
    )
    if maximum_trig != len(P3.ALLOWED_ANGLES):
        raise VerificationError("P5 trigonometric table cap mismatch")
    return p4_step1, step2, cumulative, maximum_trig


def validate_fixture(value: Any, base: Path = BASE) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError("P5 fixture must be an object")
    if canonical_sha256(value) != FIXTURE_CANONICAL_SHA256:
        raise VerificationError("P5 fixture differs from the frozen canonical object")
    require_exact_keys(
        value,
        (
            "schema_version", "fixture_id", "direct_design_parent",
            "frozen_execution_relation", "candidate_thresholds",
            "outward_arithmetic", "deterministic_resource_caps",
            "host_supervisor_caps", "conditional_authority", "scope",
        ),
        "P5 fixture",
    )
    if value["schema_version"] != 1 or value["fixture_id"] != FIXTURE_ID:
        raise SchemaError("unexpected P5 fixture identity")
    parent = value["direct_design_parent"]
    require_exact_keys(
        parent,
        (
            "commit_sha", "role", "D0_policy_id", "D0_policy_sha256",
            "D0_report_sha256", "D0_report_available_to_runner",
            "formal_caps_derived_before_this_fixture",
        ),
        "P5 design parent",
    )
    if (
        parent["commit_sha"] != REQUIRED_PARENT_COMMIT
        or parent["role"] != "direct_design_parent_only_not_a_formal_runner_input"
        or parent["D0_policy_id"]
        != "MAJORANA-P5-CONDITIONAL-STEP2-THRESHOLD-D0-V1"
        or parent["D0_report_available_to_runner"] is not False
        or parent["formal_caps_derived_before_this_fixture"] is not True
    ):
        raise VerificationError("P5 direct design-parent relation mismatch")
    require_sha256(parent["D0_policy_sha256"], "P5 D0 policy hash")
    require_sha256(parent["D0_report_sha256"], "P5 D0 report hash")
    if value["candidate_thresholds"] != _expected_candidate_rows():
        raise VerificationError("P5 candidate matrix mismatch")
    relation = value["frozen_execution_relation"]
    expected_relation = {
        "linear_size": 8,
        "n_sites": 64,
        "n_fermionic_modes": 128,
        "n_majorana_generators": 256,
        "mapped_step_indices": [1, 2],
        "composite_count_per_step": 512,
        "constituent_count_per_step": 1152,
        "truncation_boundary_count_per_step": 768,
        "step1_threshold_exponent": 34,
        "step1_threshold_rational": "1/17179869184",
        "step1_threshold_Float64_bits_hex": "3dd0000000000000",
        "candidate_step2_only": True,
        "same_process_step1_then_candidate_step2": True,
        "step1_uses_unmodified_execute_p3": True,
        "step2_uses_explicit_threshold_parameter": True,
        "step2_input_is_live_deepcopy_of_step1_retained_mainsum": True,
        "candidate_exponent_selected_only_from_CLI_and_fixture_allowlist": True,
        "no_cross_candidate_state_or_checkpoint": True,
        "step1_P3_fieldwise_conformance_required": True,
        "runner_must_not_read_P3_or_P4_result_or_D0_report": True,
        "required_base_fixture_sha256": {
            "P2": file_sha256(Path(base) / P2_FIXTURE_NAME),
            "P3": file_sha256(Path(base) / P3_FIXTURE_NAME),
            "P4": file_sha256(Path(base) / P4_FIXTURE_NAME),
        },
    }
    if relation != expected_relation:
        raise VerificationError("P5 frozen execution relation mismatch")
    arithmetic = value["outward_arithmetic"]
    if arithmetic != {
        "taylor_order": 7,
        "trig_grid_denominator": str(GRID),
        "defect_grid_denominator": str(GRID),
        "maximum_BigInt_bit_length": 2048,
        "outward_integer_binary64_RNE_oracle_required": True,
    }:
        raise VerificationError("P5 outward arithmetic mismatch")
    caps = value["deterministic_resource_caps"]
    if (
        caps.get("maximum_BigInt_bit_length") != 2048
        or caps.get("caps_are_checked_before_the_rejected_operation") is not True
        or caps.get("no_operation_occurs_after_the_first_deterministic_cap_event")
        is not True
    ):
        raise VerificationError("P5 deterministic cap semantics mismatch")
    _resource_cap_sections(value, Path(base))
    host = value["host_supervisor_caps"]
    for field in (
        "MemoryMax_bytes", "outer_safety_timeout_seconds",
        "maximum_stdout_bytes", "maximum_stderr_bytes",
    ):
        _positive_int(host.get(field), f"P5 host cap {field}")
    if (
        host.get("MemorySwapMax_bytes") != 0
        or host.get("RuntimeMaxSec") != "1200s"
        or host.get("systemd_user_scope_cgroup_v2_required") is not True
        or host.get("host_cap_failure_branch") != "INDETERMINATE"
    ):
        raise VerificationError("P5 host-supervisor policy mismatch")
    authority = value["conditional_authority"]
    if authority != {
        "formal_authority": (
            "conditional_step2_local_defect_and_Neel_enclosure_after_complete_"
            "P3_step1_conformance_only"
        ),
        "candidate_local_allocation": "1/400000",
        "conditional_two_step_cumulative_allocation": "1/200000",
        "require_all_candidates_completed": True,
        "selection_order": ["K36", "K37"],
        "runner_outputs_candidate_local_allocation_pass_only": True,
        "candidate_cumulative_allocation_pass_is_outer_checker_only": True,
        "selected_candidate_is_outer_checker_only": True,
    }:
        raise VerificationError("P5 conditional authority mismatch")
    if value["scope"] != RAW_SCOPE:
        raise VerificationError("P5 fixture scope mismatch")
    return value


_BRANCH_STATUS_DEFAULTS = {
    "K36_SELECTED_AFTER_ALL_CANDIDATES_COMPLETE": K36_SELECTED_STATUS,
    (
        "K37_SELECTED_AFTER_K36_NOT_WITHIN_BOTH_ALLOCATIONS_AND_ALL_"
        "CANDIDATES_COMPLETE"
    ): K37_SELECTED_STATUS,
    "NO_CANDIDATE_WITHIN_BOTH_ALLOCATIONS_AFTER_ALL_CANDIDATES_COMPLETE": (
        NO_CANDIDATE_STATUS
    ),
    "REQUIRED_CANDIDATE_DETERMINISTIC_POLICY_CAP_EXCEEDED": CAP_STATUS,
    "FAILED_P3_POST_REPLAY_CONFORMANCE": FAILED_CONFORMANCE_STATUS,
    "INDETERMINATE": INDETERMINATE_STATUS,
    "INVALID_REPLAY": INVALID_STATUS,
}


def validate_policy(
    value: Any, fixture: Mapping[str, Any] | None = None,
    runtime_lock: Any = None,
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError("P5 policy must be an object")
    if canonical_sha256(value) != POLICY_CANONICAL_SHA256:
        raise VerificationError("P5 policy differs from the frozen canonical object")
    require_exact_keys(
        value,
        (
            "schema_version", "policy_id", "policy_fingerprint", "policy_role",
            "required_fixture_id", "required_direct_design_parent_commit",
            "conditional_candidate_design", "parent_authority_and_telescoping",
            "allocation_enforcement", "D0_cap_provenance",
            "deterministic_resource_caps", "host_supervisor_caps",
            "runner_visibility_and_precommit_boundary",
            "selection_and_terminal_truth_table",
            "result_determinism_and_signed_zero", "proof_obligations",
            "scope_boundary", "required_adversarial_mutations",
            "terminal_branch_precedence",
        ),
        "P5 policy",
    )
    if (
        value["schema_version"] != 1
        or value["policy_id"]
        != "MAJORANA-P5-S0-CONDITIONAL-STEP2-THRESHOLD-HARDENING-V1"
        or value["required_fixture_id"] != FIXTURE_ID
        or value["required_direct_design_parent_commit"] != REQUIRED_PARENT_COMMIT
    ):
        raise SchemaError("unexpected P5 policy identity")
    candidate = value["conditional_candidate_design"]
    if (
        candidate.get("candidate_order_is_frozen_before_formal_results")
        != list(CANDIDATE_ORDER)
        or [row.get("candidate_id") for row in candidate.get("candidates", [])]
        != list(CANDIDATE_ORDER)
        or [row.get("step2_threshold_exponent") for row in candidate["candidates"]]
        != [36, 37]
        or any(row.get("step1_threshold_exponent") != 34 for row in candidate["candidates"])
        or candidate.get("both_fresh_replays_of_each_candidate_are_required") is not True
        or candidate.get("all_four_candidate_processes_must_complete_before_selection")
        is not True
        or candidate.get("K36_completion_or_pass_does_not_permit_skipping_K37")
        is not True
        or candidate.get("budget_constrained_drop_is_not_a_candidate") is not True
        or candidate.get("globally_rethresholding_both_steps_is_not_a_candidate")
        is not True
    ):
        raise VerificationError("P5 frozen candidate policy mismatch")
    parent = value["parent_authority_and_telescoping"]
    if (
        parent.get("P3_E1_charge_multiplicity_per_candidate") != 1
        or parent.get("P3_E1_numeric_value_is_forbidden_from_runner_visible_inputs")
        is not True
        or parent.get("P4_E12_or_step2_error_is_not_inherited") is not True
        or parent.get("D0_report_is_not_a_runner_input") is not True
        or parent.get("candidate_step2_product_merge_and_drop_counters_start_at_zero")
        is not True
        or parent.get("parent_error_exact_unitary_propagation_factor") != 1
    ):
        raise VerificationError("P5 parent/telescoping policy mismatch")
    allocation = value["allocation_enforcement"]
    if (
        Fraction(allocation.get("candidate_step2_local_allocation"))
        != STEP2_ALLOCATION
        or Fraction(allocation.get("conditional_two_step_cumulative_allocation"))
        != CUMULATIVE_ALLOCATION
        or allocation.get("equality_is_failure") is not True
        or allocation.get("candidate_positive_iff_local_and_cumulative_pass") is not True
        or allocation.get("allocation_comparisons_use_exact_integer_cross_multiplication_only")
        is not True
        or allocation.get("outer_checker_alone_composes_P3_E1_and_emits_candidate_cumulative_pass")
        is not True
    ):
        raise VerificationError("P5 allocation policy mismatch")
    provenance = value["D0_cap_provenance"]
    if (
        provenance.get("D0_policy_sha256")
        != "e47ad24291f217b0b5d54ba6aa120c479d522bd23c74faf41b5bde6da2413aa2"
        or provenance.get("D0_report_sha256")
        != "602c4eddea30c20ddb793e2641b1e8b55e4767a62366b946892a19c3802dffc5"
        or provenance.get("D0_report_commit_sha") != REQUIRED_PARENT_COMMIT
        or provenance.get("formal_candidates_were_frozen_before_D0") != [36, 37]
        or provenance.get("both_formal_candidates_completed_D0_without_host_or_deterministic_cap")
        is not True
        or provenance.get("one_common_cap_set_applies_identically_to_K36_and_K37")
        is not True
        or provenance.get("D0_report_bytes_are_forbidden_from_runner_staging")
        is not True
        or provenance.get("D0_report_does_not_select_remove_reorder_or_rank_formal_candidates")
        is not True
    ):
        raise VerificationError("P5 D0 provenance policy mismatch")
    truth = value["selection_and_terminal_truth_table"]
    branches = {
        row.get("branch"): row.get("maximum_status")
        for row in truth.get("legal_terminal_branches", [])
        if isinstance(row, dict)
    }
    if branches != _BRANCH_STATUS_DEFAULTS:
        raise VerificationError("P5 terminal branch/status map mismatch")
    if (
        truth.get("selection_is_outer_checker_only") is not True
        or truth.get("K36_is_selected_when_both_candidates_pass") is not True
        or truth.get("smaller_observed_bound_does_not_override_frozen_K36_priority")
        is not True
        or truth.get("a_required_candidate_cap_host_failure_invalid_replay_or_missing_replay_forbids_a_winner")
        is not True
    ):
        raise VerificationError("P5 complete-candidate selector mismatch")
    visibility = value["runner_visibility_and_precommit_boundary"]
    if (
        visibility.get("runner_must_not_read_P3_result_contract_certificate_witness_or_numeric_E1")
        is not True
        or visibility.get("runner_must_not_read_P4_result_contract_certificate_witness_or_numeric_result")
        is not True
        or visibility.get("runner_must_not_read_D0_policy_or_report_bytes") is not True
        or visibility.get("outer_checker_may_read_pinned_P3_results_only_after_all_raw_candidate_processes_finish")
        is not True
        or visibility.get("formal_precommit_must_exclude_P5_raw_transcripts_witnesses_result_contract_certificate_and_exact_result_test")
        is not True
        or not isinstance(visibility.get("forbidden_formal_result_pins"), list)
    ):
        raise VerificationError("P5 result-blind runner policy mismatch")
    determinism = value["result_determinism_and_signed_zero"]
    if (
        determinism.get("both_raw_transcripts_for_each_candidate_must_be_byte_identical")
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
        raise VerificationError("P5 signed-zero/determinism policy mismatch")
    scope = value["scope_boundary"]
    if (
        scope.get("only_step2_is_hardened_to_K36_or_K37") is not True
        or scope.get("uniform_2^-36_or_2^-37_threshold_across_both_steps")
        != "NOT_ASSESSED"
        or scope.get("budget_constrained_drop") != "NOT_ASSESSED"
        or scope.get("physical_reference_qualified") is not False
        or scope.get("ready_gate_eligible") is not False
    ):
        raise VerificationError("P5 scope boundary mismatch")
    if fixture is not None:
        if value["deterministic_resource_caps"] != {
            **fixture["deterministic_resource_caps"],
            "cap_scope": (
                "common_candidate_step2_local_caps_after_a_complete_fresh_"
                "P3_compatible_step1_reconstruction"
            ),
            "maximum_two_step_accuracy_charged_events": 35651584,
            "maximum_two_step_total_P2_charged_term_visits": 1140850688,
            "maximum_two_step_total_P2_plus_accuracy_charged_events": 1140850688,
            "step1_reconstruction_remains_subject_to_the_pinned_P3_and_P2_caps": True,
            "caps_are_checked_before_the_corresponding_scan_allocation_or_accuracy_operation": True,
            "BigInt_bit_length_is_checked_after_each_tick_computation_and_cumulative_update": True,
            "common_caps_cannot_be_relaxed_for_only_one_candidate": True,
            "any_required_candidate_cap_precludes_candidate_selection": True,
            "a_cap_branch_has_resource_guard_authority_only_not_allocation_failure_authority": True,
        }:
            raise VerificationError("P5 fixture/policy resource caps differ")
        expected_host_subset = fixture["host_supervisor_caps"]
        for key, expected in expected_host_subset.items():
            policy_key = (
                "host_cap_or_supervisor_failure_branch"
                if key == "host_cap_failure_branch" else key
            )
            if value["host_supervisor_caps"].get(policy_key) != expected:
                raise VerificationError(f"P5 fixture/policy host cap differs: {key}")
    if runtime_lock is not None:
        P0.validate_runtime_lock(runtime_lock)
    return value


def validate_precommit_contract(
    value: Any, base: Path = BASE, *, verify_source_files: bool = True,
) -> Mapping[str, Any]:
    base = Path(base)
    if not isinstance(value, dict):
        raise SchemaError("P5 precommit contract must be an object")
    require_exact_keys(
        value,
        (
            "schema_version", "contract_type", "self_relative_path",
            "required_parent_commit", "result_artifacts_required_absent",
            "forbidden_formal_result_pins", "source_files",
            "runner_staged_files", "runner_forbidden_paths",
        ),
        "P5 precommit contract",
    )
    if (
        value["schema_version"] != 1
        or value["contract_type"] != PRECOMMIT_CONTRACT_TYPE
        or value["self_relative_path"] != PRECOMMIT_CONTRACT_NAME
        or value["required_parent_commit"] != REQUIRED_PARENT_COMMIT
    ):
        raise VerificationError("P5 precommit identity or parent mismatch")
    fixture = validate_fixture(load_json(base / FIXTURE_NAME), base)
    policy = validate_policy(load_json(base / POLICY_NAME), fixture)
    forbidden_pins = policy["runner_visibility_and_precommit_boundary"][
        "forbidden_formal_result_pins"
    ]
    if value["forbidden_formal_result_pins"] != forbidden_pins:
        raise VerificationError("P5 forbidden result pins mismatch")
    if tuple(value["result_artifacts_required_absent"]) != (
        RESULT_CONTRACT_NAME, CERTIFICATE_NAME, RESULT_TEST_NAME,
    ):
        raise VerificationError("P5 result artifact absence set mismatch")
    if tuple(value["runner_staged_files"]) != RUNNER_STAGED_PATHS:
        raise VerificationError("P5 runner staging allowlist mismatch")
    if tuple(value["runner_forbidden_paths"]) != RUNNER_FORBIDDEN_PATHS:
        raise VerificationError("P5 runner forbidden path set mismatch")
    rows = value["source_files"]
    if not isinstance(rows, list):
        raise SchemaError("P5 source_files must be an array")
    paths: list[str] = []
    for row in rows:
        require_exact_keys(row, ("relative_path", "size_bytes", "sha256"), "P5 source row")
        relative = row["relative_path"]
        if (
            not isinstance(relative, str) or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise SchemaError("invalid P5 source relative path")
        if type(row["size_bytes"]) is not int or row["size_bytes"] < 0:
            raise SchemaError("invalid P5 source size")
        require_sha256(row["sha256"], f"P5 source hash {relative}")
        if verify_source_files:
            path = base / relative
            if path.is_symlink() or not path.is_file():
                raise VerificationError(f"P5 source is not a regular file: {relative}")
            if path.stat().st_size != row["size_bytes"] or file_sha256(path) != row["sha256"]:
                raise VerificationError(f"P5 source custody mismatch: {relative}")
        paths.append(relative)
    if tuple(paths) != PRECOMMIT_SOURCE_PATHS:
        raise VerificationError("P5 source custody allowlist mismatch")
    if not set(RUNNER_STAGED_PATHS).issubset(paths):
        raise VerificationError("P5 runner stage is outside source custody")
    if set(RUNNER_STAGED_PATHS) & set(RUNNER_FORBIDDEN_PATHS):
        raise VerificationError("P5 runner stage exposes a forbidden result")
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
            raise VerificationError("P5 signed-zero/identity micro-oracle mismatch")
        digest = hashlib.sha256()
        for mask in range(1 << 16):
            bits = P4._upstream_fock_real_bits(mask, occupied)
            digest.update(f"{mask:x}\t{bits:016x}\n".encode("ascii"))
        if digest.hexdigest() != _SIGNED_ZERO_MICRO_ORACLE_SHA256:
            raise VerificationError("P5 signed-zero micro-oracle digest mismatch")
        _signed_zero_micro_oracle_checked = True


def _candidate_descriptor(candidate_id: str) -> dict[str, Any]:
    if candidate_id not in CANDIDATE_BITS:
        raise SchemaError("unknown P5 candidate")
    exponent = CANDIDATE_EXPONENTS[candidate_id]
    return {
        "candidate_id": candidate_id,
        "identity": f"step1_fixed_2^-34_then_step2_fixed_2^-{exponent}",
        "required_fresh_process_count": 2,
        "step1_threshold_exponent": 34,
        "step1_threshold_rational": "1/17179869184",
        "step1_threshold_Float64_bits_hex": "3dd0000000000000",
        "step2_threshold_exponent": exponent,
        "step2_threshold_rational": f"1/{1 << exponent}",
        "step2_threshold_Float64_bits_hex": f"{CANDIDATE_BITS[candidate_id]:016x}",
        "strict_drop_rule": (
            "abs_binary64_coefficient_strictly_less_than_threshold"
        ),
        "step1_path_is_not_rethresholded": True,
    }


def _state_descriptor(state: Mapping[int, int]) -> dict[str, Any]:
    return P4._state_descriptor(state)


def replay_candidate_oracle(
    trig_table: Mapping[str, Any], fixture: Mapping[str, Any],
    candidate_id: str, base: Path = BASE,
) -> dict[str, Any]:
    """Reconstruct one result-blind candidate with isolated threshold globals."""

    base = Path(base)
    if candidate_id not in CANDIDATE_ORDER:
        raise SchemaError("unknown P5 oracle candidate")
    trig = P3._validate_trig_table(trig_table)
    schedule = P3.expected_schedule()
    step1_caps, step2_caps, cumulative_caps, maximum_trig = _resource_cap_sections(
        fixture, base,
    )
    if len(trig) != maximum_trig:
        raise VerificationError("P5 raw trigonometric table exceeds its frozen cap")
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
            local_pass = None
            if step1["execution"]["cap_event"] is None:
                if step1["final_state"] is None:
                    raise VerificationError("completed P5 step1 lacks a final state")
                step2_input = _state_descriptor(state)
                if (
                    step2_input["term_count"]
                    != step1["final_state"]["retained_term_count"]
                    or step2_input["term_stream_sha256"]
                    != step1["final_state"]["term_stream_sha256"]
                ):
                    raise VerificationError("P5 oracle step boundary does not link")
                state = dict(state)
                P4.EPSILON_BITS = CANDIDATE_BITS[candidate_id]
                step2, state = P4._run_step_oracle(
                    step_index=2, state=state, trig=trig, schedule=schedule,
                    step_caps=step2_caps, cumulative_caps=cumulative_caps,
                    cumulative=cumulative, maximum_bits=maximum_bits,
                    input_state=step2_input,
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
                if step2["execution"]["cap_event"] is None:
                    ticks = int(step2["accuracy_ledger"]["total_operator_error_ticks"])
                    local_pass = ticks * 400000 < GRID
        finally:
            P4.EPSILON_BITS = previous_epsilon
    return {
        "candidate": _candidate_descriptor(candidate_id),
        "step1": step1,
        "step_boundary_link": link,
        "step2": step2,
        "candidate_local_allocation_pass": local_pass,
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
        raise SchemaError("P5 raw witness must be an object")
    require_exact_keys(
        witness,
        (
            "schema_version", "witness_type", "fixture_id", "fixture_sha256",
            "fixture_canonical_sha256", "inherited_P4_fixture_sha256",
            "inherited_P4_fixture_canonical_sha256",
            "inherited_P3_fixture_sha256",
            "inherited_P3_fixture_canonical_sha256",
            "inherited_P2_fixture_sha256",
            "inherited_P2_fixture_canonical_sha256", "runtime", "upstream",
            "initial_observable", "schedule", "trig_table", "candidate",
            "step1", "step_boundary_link", "step2",
            "candidate_local_allocation_pass", "scope",
        ),
        "P5 raw witness",
    )
    if (
        witness["schema_version"] != 1
        or witness["witness_type"] != RAW_WITNESS_TYPE
        or witness["fixture_id"] != fixture["fixture_id"]
    ):
        raise SchemaError("unexpected P5 raw witness identity")
    fixture_path = base / FIXTURE_NAME
    if (
        witness["fixture_sha256"] != file_sha256(fixture_path)
        or witness["fixture_canonical_sha256"] != canonical_sha256(fixture)
    ):
        raise VerificationError("P5 raw fixture custody mismatch")
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
                    f"P5 raw inherited {prefix} fixture custody mismatch"
                )
    if witness["runtime"] != P2._expected_runtime(runtime_lock):
        raise VerificationError("P5 raw runtime custody mismatch")
    if witness["upstream"] != P2._expected_upstream(runtime_lock):
        raise VerificationError("P5 raw upstream custody mismatch")
    if witness["initial_observable"] != P2.expected_initial_observable():
        raise VerificationError("P5 raw initial observable mismatch")
    if witness["schedule"] != P3.expected_schedule():
        raise VerificationError("P5 raw schedule mismatch")
    if witness["scope"] != RAW_SCOPE or witness["scope"] != fixture["scope"]:
        raise VerificationError("P5 raw scope exceeds execution-only authority")
    candidate_id = witness["candidate"].get("candidate_id") \
        if isinstance(witness["candidate"], dict) else None
    if candidate_id not in CANDIDATE_ORDER:
        raise SchemaError("P5 raw candidate identity is not allowed")
    if expected_candidate_id is not None and candidate_id != expected_candidate_id:
        raise VerificationError("P5 raw candidate differs from its outer process binding")
    oracle = replay_candidate_oracle(
        witness["trig_table"], fixture, candidate_id, base,
    )
    for field in (
        "candidate", "step1", "step_boundary_link", "step2",
        "candidate_local_allocation_pass",
    ):
        _assert_fieldwise_equal(
            witness[field], oracle[field], f"P5 {candidate_id} raw {field}",
        )
    step1 = witness["step1"]
    step2 = witness["step2"]
    if step1["execution"]["cap_event"] is not None:
        if step2 is not None or witness["step_boundary_link"] is not None:
            raise VerificationError("P5 capped step1 has an attempted step2")
    else:
        if step2 is None or witness["step_boundary_link"] is None:
            raise VerificationError("P5 completed step1 lacks its same-process step2")
        link = witness["step_boundary_link"]
        if (
            link["same_process"] is not True or link["no_serialization"] is not True
            or link["step1_output_term_count"] != link["step2_input_term_count"]
            or link["step1_output_term_stream_sha256"]
            != link["step2_input_term_stream_sha256"]
        ):
            raise VerificationError("P5 raw step boundary is not same-process linked")
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


def _next_power_of_two_at_least_twice(value: int) -> int:
    _positive_int(value, "D0 completed resource observation")
    target = 2 * value
    return 1 << (target - 1).bit_length()


def _derive_step2_caps_from_d0(report: Mapping[str, Any]) -> dict[str, int]:
    observations: dict[int, Mapping[str, Any]] = {}
    for row in report.get("observations", []):
        if not isinstance(row, dict):
            raise SchemaError("P5 D0 observation must be an object")
        exponent = row.get("step2_threshold_exponent")
        if exponent not in (36, 37):
            continue
        if (
            row.get("status") != "COMPLETED_RESOURCE_OBSERVATION"
            or row.get("process_returncode") != 0
            or row.get("outer_timeout_triggered") is not False
        ):
            raise VerificationError("P5 D0 formal candidate did not complete")
        witness = row.get("resource_witness")
        if (
            not isinstance(witness, dict)
            or witness.get("scientific_authority") != "NONE"
            or witness.get("resource_observations_only") is not True
            or witness.get("certificate_eligible") is not False
            or witness.get("candidate", {}).get("step2_threshold_exponent") != exponent
            or witness.get("step1", {}).get("cap_event") is not None
            or witness.get("step2", {}).get("cap_event") is not None
        ):
            raise VerificationError("P5 D0 candidate observation authority mismatch")
        if exponent in observations:
            raise VerificationError("duplicate P5 D0 candidate observation")
        observations[exponent] = witness["step2"]
    if set(observations) != {36, 37}:
        raise VerificationError("P5 D0 report lacks both formal candidate observations")

    def maximum(path: Sequence[str]) -> int:
        values: list[int] = []
        for exponent in (36, 37):
            value: Any = observations[exponent]
            for key in path:
                if not isinstance(value, dict) or key not in value:
                    raise SchemaError(f"P5 D0 resource path missing: {'.'.join(path)}")
                value = value[key]
            values.append(_positive_int(value, f"P5 D0 {'.'.join(path)}"))
        return max(values)

    observed_paths = {
        # A retained/current state is bounded by the reported post-merge peak;
        # using that larger observable also covers every boundary/final count.
        "maximum_current_terms_before_constituent": (
            "peak_postmerge_unique_term_count",
        ),
        "maximum_premerge_terms": ("peak_premerge_contribution_count",),
        "maximum_boundary_retained_terms": (
            "peak_postmerge_unique_term_count",
        ),
        "maximum_cap_scan_term_visits": (
            "P2_resource_counters", "cap_scan_term_visits",
        ),
        "maximum_propagation_term_visits": (
            "P2_resource_counters", "propagation_term_visits",
        ),
        "maximum_truncation_term_visits": (
            "P2_resource_counters", "truncation_term_visits",
        ),
        "maximum_final_evaluation_term_visits": ("final_retained_term_count",),
        "maximum_total_charged_term_visits": (
            "P2_resource_counters", "total_charged_term_visits",
        ),
        "maximum_anticommuting_events": (
            "accuracy_event_counters", "anticommuting_event_count",
        ),
        "maximum_product_defect_events": (
            "accuracy_event_counters", "product_defect_event_count",
        ),
        "maximum_merge_defect_events": (
            "accuracy_event_counters", "merge_defect_event_count",
        ),
        "maximum_drop_defect_events": (
            "accuracy_event_counters", "drop_defect_event_count",
        ),
        "maximum_accuracy_charged_events": (
            "accuracy_event_counters", "accuracy_charged_event_count",
        ),
        "maximum_total_P2_plus_accuracy_charged_events": (
            "total_P2_plus_accuracy_charged_event_count",
        ),
    }
    derived = {
        key: _next_power_of_two_at_least_twice(maximum(path))
        for key, path in observed_paths.items()
    }
    derived.update({
        "maximum_composites": 512,
        "maximum_constituents": 1152,
        "maximum_truncation_boundaries": 768,
    })
    return derived


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
            "P5 precommit changed-path set differs from the exact six-file allowlist"
        )
    return list(changed)


def _verify_design_parent_and_authority(
    fixture: Mapping[str, Any], policy: Mapping[str, Any], base: Path = BASE,
) -> tuple[
    Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]
]:
    """Open D0 and P3/P4 result bytes only after all raw processes finish."""

    base = Path(base)
    repo, _base_relative = P2._repo_and_base_relative(base)
    resolved = P2._run_git(repo, "rev-parse", REQUIRED_PARENT_COMMIT).stdout.decode().strip()
    if resolved != REQUIRED_PARENT_COMMIT:
        raise VerificationError("P5 direct design parent does not resolve exactly")
    p4_is_ancestor = P2._run_git(
        repo, "merge-base", "--is-ancestor", P4_RESULT_COMMIT,
        REQUIRED_PARENT_COMMIT, check=False,
    )
    p3_is_ancestor = P2._run_git(
        repo, "merge-base", "--is-ancestor", P3_RESULT_COMMIT,
        P4_RESULT_COMMIT, check=False,
    )
    if p4_is_ancestor.returncode != 0 or p3_is_ancestor.returncode != 0:
        raise VerificationError("P5 P3/P4/design-parent ancestry mismatch")

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
        raise VerificationError("P5 D0 design-parent custody mismatch")
    d0_policy = load_json(d0_policy_path)
    d0_report = load_json(d0_report_path)
    if (
        d0_policy.get("schema_version") != 1
        or d0_policy.get("policy_id") != parent["D0_policy_id"]
        or d0_policy.get("scientific_authority") != "NONE"
        or d0_policy.get("certificate_eligible") is not False
        or d0_report.get("schema_version") != 1
        or d0_report.get("report_type")
        != "majorana_p5_conditional_step2_threshold_resource_report_d0_v1"
        or d0_report.get("policy_id") != parent["D0_policy_id"]
        or d0_report.get("policy_sha256") != parent["D0_policy_sha256"]
        or d0_report.get("scientific_authority") != "NONE"
        or d0_report.get("certificate_eligible") is not False
        or d0_report.get("formal_candidates_were_frozen_before_probe") != [36, 37]
        or d0_report.get("probe_results_must_not_be_runner_inputs_for_formal_P5")
        is not True
        or d0_report.get("probe_results_must_not_select_or_remove_formal_candidates")
        is not True
    ):
        raise VerificationError("P5 D0 semantic provenance mismatch")
    derived = _derive_step2_caps_from_d0(d0_report)
    _step1, formal_step2, _cumulative, _maximum_trig = _resource_cap_sections(
        fixture, base,
    )
    if derived != formal_step2:
        raise VerificationError("P5 formal caps are not the frozen D0 derivation")
    if policy["D0_cap_provenance"]["D0_report_sha256"] != file_sha256(d0_report_path):
        raise VerificationError("P5 policy/D0 report custody mismatch")

    for relative in (
        P4_RESULT_CONTRACT_NAME, P4_CERTIFICATE_NAME, P4_RESULT_TEST_NAME,
    ):
        path = base / relative
        if _git_committed_bytes(base, P4_RESULT_COMMIT, relative) != path.read_bytes():
            raise VerificationError(f"P5 active P4 result drifted: {relative}")
    with _p4_module_base(base):
        p4_summary = P4.verify_final(base)
        p4_fixture = P4.validate_fixture(load_json(base / P4_FIXTURE_NAME))
        p3_summary, p3_result, p3_witness = P4._verify_parent_p3(
            p4_fixture, base,
        )
    if (
        p4_summary["status"] != P4.EXCEEDS_STATUS
        or p3_summary["status"] != P4.PARENT_STATUS
        or p3_result["status"] != P4.PARENT_STATUS
    ):
        raise VerificationError("P5 required P3/P4 authority status mismatch")
    return d0_report, p4_summary, p3_result, p3_witness


def _status_for_terminal_branch(policy: Mapping[str, Any], branch: str) -> str:
    statuses = {
        row["branch"]: row["maximum_status"]
        for row in policy["selection_and_terminal_truth_table"][
            "legal_terminal_branches"
        ]
    }
    if branch not in statuses:
        raise VerificationError("illegal P5 terminal branch")
    return statuses[branch]


def _authoritative_final_state(
    raw_step2_final: Mapping[str, Any], cumulative_ticks: int,
) -> dict[str, Any]:
    return P4._authoritative_final_state(raw_step2_final, cumulative_ticks)


def _compose_authoritative_witness(
    raws: Mapping[str, Mapping[str, Any]], fixture: Mapping[str, Any],
    policy: Mapping[str, Any], base: Path = BASE,
) -> dict[str, Any]:
    """After raw validation, inherit P3 E1 once and run the frozen selector."""

    base = Path(base)
    if tuple(raws) != CANDIDATE_ORDER:
        raise VerificationError("P5 composed raw candidate order mismatch")
    d0_report, p4_summary, p3_result, p3_witness = (
        _verify_design_parent_and_authority(fixture, policy, base)
    )
    parent_ledger = p3_witness["accuracy_ledger"]
    if parent_ledger["grid_denominator"] != str(GRID):
        raise VerificationError("P5 parent P3 defect grid mismatch")

    cap_candidates: list[str] = []
    projections: dict[str, dict[str, Any]] = {}
    for candidate_id in CANDIDATE_ORDER:
        raw = raws[candidate_id]
        step1 = raw["step1"]
        step2 = raw["step2"]
        if step1["execution"]["cap_event"] is not None:
            cap_candidates.append(candidate_id)
            continue
        projection = _step1_p3_projection(raw, base)
        projections[candidate_id] = projection
        if step2 is None or step2["execution"]["cap_event"] is not None:
            cap_candidates.append(candidate_id)

    candidate_rows: list[dict[str, Any]] = []
    selected_candidate: str | None = None
    selected_final_state: Mapping[str, Any] | None = None
    p3_conformance_complete = False
    if cap_candidates:
        branch = "REQUIRED_CANDIDATE_DETERMINISTIC_POLICY_CAP_EXCEEDED"
        for candidate_id in CANDIDATE_ORDER:
            raw = raws[candidate_id]
            cap = raw["step1"]["execution"]["cap_event"]
            if cap is None and raw["step2"] is not None:
                cap = raw["step2"]["execution"]["cap_event"]
            candidate_rows.append({
                "candidate_id": candidate_id,
                "raw_witness_sha256": canonical_sha256(raw),
                "completed_without_policy_cap": cap is None,
                "first_policy_cap_event": cap,
                "step1_P3_projection_sha256": (
                    canonical_sha256(projections[candidate_id])
                    if candidate_id in projections else None
                ),
                "step1_P3_fieldwise_conformance": None,
                "parent_P3_E1_inherited": False,
                "telescoping_ledger": None,
                "authoritative_two_step_final_state": None,
            })
    else:
        # No numeric P3 charge is inherited before every complete prefix agrees
        # with the single certified parent witness field by field.
        conformance: dict[str, bool] = {}
        for candidate_id in CANDIDATE_ORDER:
            try:
                _assert_fieldwise_equal(
                    projections[candidate_id], p3_witness,
                    f"P5 {candidate_id} fresh step1 P3 conformance",
                )
            except VerificationError:
                conformance[candidate_id] = False
            else:
                conformance[candidate_id] = True
        try:
            _assert_fieldwise_equal(
                projections["K36"], projections["K37"],
                "P5 cross-candidate step1 fieldwise conformance",
            )
        except VerificationError:
            cross_candidate_conformance = False
        else:
            cross_candidate_conformance = True

        if not all(conformance.values()) or not cross_candidate_conformance:
            branch = "FAILED_P3_POST_REPLAY_CONFORMANCE"
            for candidate_id in CANDIDATE_ORDER:
                raw = raws[candidate_id]
                candidate_rows.append({
                    "candidate_id": candidate_id,
                    "raw_witness_sha256": canonical_sha256(raw),
                    "completed_without_policy_cap": True,
                    "first_policy_cap_event": None,
                    "step1_P3_projection_sha256": canonical_sha256(
                        projections[candidate_id]
                    ),
                    "step1_P3_fieldwise_conformance": (
                        conformance[candidate_id] and cross_candidate_conformance
                    ),
                    "parent_P3_E1_inherited": False,
                    "telescoping_ledger": None,
                    "authoritative_two_step_final_state": None,
                })
        else:
            p3_conformance_complete = True
            # The numeric P3 E1 is not even decoded until every complete
            # candidate prefix has passed parent and cross-candidate
            # fieldwise conformance.
            parent_ticks = int(parent_ledger["total_operator_error_ticks"])
            positives: dict[str, bool] = {}
            for candidate_id in CANDIDATE_ORDER:
                raw = raws[candidate_id]
                step1_ticks = int(
                    raw["step1"]["accuracy_ledger"]["total_operator_error_ticks"]
                )
                if step1_ticks != parent_ticks:
                    raise VerificationError("P5 fresh step1 ticks differ from P3 E1")
                step2 = raw["step2"]
                assert step2 is not None and step2["final_state"] is not None
                local_ledger = step2["accuracy_ledger"]
                if local_ledger["grid_denominator"] != str(GRID):
                    raise VerificationError("P5 candidate local defect grid mismatch")
                local_ticks = int(local_ledger["total_operator_error_ticks"])
                cumulative_ticks = parent_ticks + local_ticks
                local_pass = local_ticks * 400000 < GRID
                cumulative_pass = cumulative_ticks * 200000 < GRID
                if raw["candidate_local_allocation_pass"] is not local_pass:
                    raise VerificationError("P5 runner/checker local allocation truth mismatch")
                if local_pass and not cumulative_pass:
                    raise VerificationError(
                        "P5 local-pass/cumulative-fail truth is impossible after P3 conformance"
                    )
                positive = local_pass and cumulative_pass
                positives[candidate_id] = positive
                telescoping = {
                    "grid_denominator": str(GRID),
                    "parent_P3_operator_error_ticks": str(parent_ticks),
                    "fresh_step1_recomputed_operator_error_ticks": str(step1_ticks),
                    "fresh_step1_recomputed_ticks_equal_parent": True,
                    "fresh_step1_recomputation_is_conformance_not_a_second_charge": True,
                    "parent_step1_error_charge_multiplicity": 1,
                    "exact_unitary_parent_error_propagation_factor": 1,
                    "candidate_step2_product_defect_ticks": local_ledger[
                        "product_defect_ticks"
                    ],
                    "candidate_step2_merge_defect_ticks": local_ledger[
                        "merge_defect_ticks"
                    ],
                    "candidate_step2_drop_defect_ticks": local_ledger[
                        "drop_defect_ticks"
                    ],
                    "candidate_step2_local_increment_ticks": str(local_ticks),
                    "candidate_cumulative_two_step_operator_error_ticks": str(
                        cumulative_ticks
                    ),
                    "composition_identity": (
                        "parent_P3_E1_once_plus_candidate_step2_local_increment"
                    ),
                    "P4_E12_or_step2_error_inherited": False,
                    "parent_ticks_not_requantized_rounded_or_widened_again": True,
                    "outward_widening_not_double_counted": True,
                    "candidate_step2_local_allocation": "1/400000",
                    "candidate_step2_strictly_within_allocation": local_pass,
                    "candidate_step2_strict_integer_comparison": (
                        "candidate_local_ticks_times_400000_less_than_grid_denominator"
                    ),
                    "conditional_two_step_cumulative_allocation": "1/200000",
                    "candidate_cumulative_strictly_within_allocation": cumulative_pass,
                    "candidate_cumulative_strict_integer_comparison": (
                        "candidate_cumulative_ticks_times_200000_less_than_grid_denominator"
                    ),
                    "candidate_positive_iff_both_strict_comparisons": positive,
                }
                final_state = _authoritative_final_state(
                    step2["final_state"], cumulative_ticks,
                )
                candidate_rows.append({
                    "candidate_id": candidate_id,
                    "raw_witness_sha256": canonical_sha256(raw),
                    "completed_without_policy_cap": True,
                    "first_policy_cap_event": None,
                    "step1_P3_projection_sha256": canonical_sha256(
                        projections[candidate_id]
                    ),
                    "step1_P3_fieldwise_conformance": True,
                    "parent_P3_E1_inherited": True,
                    "telescoping_ledger": telescoping,
                    "authoritative_two_step_final_state": final_state,
                })
            if positives["K36"]:
                branch = "K36_SELECTED_AFTER_ALL_CANDIDATES_COMPLETE"
                selected_candidate = "K36"
            elif positives["K37"]:
                branch = (
                    "K37_SELECTED_AFTER_K36_NOT_WITHIN_BOTH_ALLOCATIONS_AND_ALL_"
                    "CANDIDATES_COMPLETE"
                )
                selected_candidate = "K37"
            else:
                branch = (
                    "NO_CANDIDATE_WITHIN_BOTH_ALLOCATIONS_AFTER_ALL_CANDIDATES_COMPLETE"
                )
            if selected_candidate is not None:
                selected_final_state = next(
                    row["authoritative_two_step_final_state"]
                    for row in candidate_rows
                    if row["candidate_id"] == selected_candidate
                )

    status = _status_for_terminal_branch(policy, branch)
    return {
        "schema_version": 1,
        "witness_type": COMPOSED_WITNESS_TYPE,
        "fixture_id": fixture["fixture_id"],
        "fixture_sha256": file_sha256(base / FIXTURE_NAME),
        "fixture_canonical_sha256": canonical_sha256(fixture),
        "raw_witnesses_sha256_by_candidate": {
            candidate_id: canonical_sha256(raws[candidate_id])
            for candidate_id in CANDIDATE_ORDER
        },
        "raw_witnesses_by_candidate": {
            candidate_id: raws[candidate_id] for candidate_id in CANDIDATE_ORDER
        },
        "design_parent_D0": {
            "commit_sha": REQUIRED_PARENT_COMMIT,
            "policy_sha256": file_sha256(base / D0_POLICY_NAME),
            "report_sha256": file_sha256(base / D0_REPORT_NAME),
            "report_type": d0_report["report_type"],
            "scientific_authority": "NONE",
            "used_only_to_verify_pre_registered_common_resource_caps": True,
            "candidate_selection_or_scientific_error_evidence_used": False,
        },
        "parent_P4_lineage": {
            "result_commit_sha": P4_RESULT_COMMIT,
            "status": p4_summary["status"],
            "result_contract_sha256": file_sha256(base / P4_RESULT_CONTRACT_NAME),
            "certificate_sha256": file_sha256(base / P4_CERTIFICATE_NAME),
            "numeric_E12_or_step2_error_inherited": False,
        },
        "parent_P3_authority": {
            "result_commit_sha": P3_RESULT_COMMIT,
            "status": p3_result["status"],
            "terminal_branch": p3_result["terminal_branch"],
            "result_contract_sha256": file_sha256(base / P3_RESULT_CONTRACT_NAME),
            "certificate_sha256": file_sha256(base / P3_CERTIFICATE_NAME),
            "canonical_witness_sha256": p3_result["canonical_witness_sha256"],
            "accuracy_ledger_sha256": canonical_sha256(parent_ledger),
            "E1_charge_multiplicity_per_completed_candidate": (
                1 if p3_conformance_complete else 0
            ),
        },
        "candidate_results": candidate_rows,
        "all_candidates_completed_before_selection": not cap_candidates,
        "selection_order": list(CANDIDATE_ORDER),
        "selected_candidate_id": selected_candidate,
        "selected_authoritative_two_step_final_state": selected_final_state,
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
        raise SchemaError("P5 composed witness must be an object")
    require_exact_keys(
        witness,
        (
            "schema_version", "witness_type", "fixture_id", "fixture_sha256",
            "fixture_canonical_sha256", "raw_witnesses_sha256_by_candidate",
            "raw_witnesses_by_candidate", "design_parent_D0",
            "parent_P4_lineage", "parent_P3_authority", "candidate_results",
            "all_candidates_completed_before_selection", "selection_order",
            "selected_candidate_id", "selected_authoritative_two_step_final_state",
            "terminal_branch", "status", "scope",
        ),
        "P5 composed witness",
    )
    raw_map = witness["raw_witnesses_by_candidate"]
    if not isinstance(raw_map, dict) or tuple(raw_map) != CANDIDATE_ORDER:
        raise SchemaError("P5 composed raw witness map mismatch")
    validated: dict[str, Mapping[str, Any]] = {}
    for candidate_id in CANDIDATE_ORDER:
        validated[candidate_id] = validate_raw_witness(
            raw_map[candidate_id], fixture, runtime_lock, candidate_id, base,
        )
    expected = _compose_authoritative_witness(validated, fixture, policy, base)
    _assert_fieldwise_equal(witness, expected, "P5 composed witness")
    return witness


def verify_precommit(base: Path = BASE) -> dict[str, Any]:
    base = Path(base)
    fixture = validate_fixture(load_json(base / FIXTURE_NAME), base)
    runtime_lock = P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), fixture, runtime_lock)
    contract = validate_precommit_contract(
        load_json(base / PRECOMMIT_CONTRACT_NAME), base,
    )
    repo, _base_relative = P2._repo_and_base_relative(base)
    resolved = P2._run_git(repo, "rev-parse", REQUIRED_PARENT_COMMIT).stdout.decode().strip()
    if resolved != REQUIRED_PARENT_COMMIT:
        raise VerificationError("P5 precommit direct design parent does not resolve")
    for artifact in contract["result_artifacts_required_absent"]:
        if (base / artifact).exists():
            raise VerificationError(f"P5 result artifact exists at precommit: {artifact}")
    return {
        "scope_ceiling": MAXIMUM_STATUS,
        "required_parent_commit": REQUIRED_PARENT_COMMIT,
        "fixture_id": fixture["fixture_id"],
        "policy_id": policy["policy_id"],
        "candidate_order": list(CANDIDATE_ORDER),
        "fresh_process_count": 4,
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
                raise VerificationError(f"P5 committed outer input differs from pin: {relative}")
        elif body != (Path(base) / PRECOMMIT_CONTRACT_NAME).read_bytes():
            raise VerificationError("P5 committed precommit contract differs from active bytes")
        rows.append({
            "relative_path": relative,
            "git_mode": mode,
            "git_blob": blob,
            "size_bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        })
    for relative in contract["result_artifacts_required_absent"]:
        if P2._git_path_exists(repo, commit, (base_relative / relative).as_posix()):
            raise VerificationError(f"P5 result artifact exists in precommit: {relative}")
    return rows


def _stage_runner_tree(
    repo: Path, base_relative: Path, commit: str,
    contract: Mapping[str, Any], destination: Path,
) -> list[dict[str, Any]]:
    pins = {row["relative_path"]: row for row in contract["source_files"]}
    if tuple(contract["runner_staged_files"]) != RUNNER_STAGED_PATHS:
        raise VerificationError("P5 runner staging allowlist drift")
    rows: list[dict[str, Any]] = []
    for relative in RUNNER_STAGED_PATHS:
        mode, blob, body = P2._git_blob(
            repo, commit, (base_relative / relative).as_posix(),
        )
        pin = pins[relative]
        if len(body) != pin["size_bytes"] or hashlib.sha256(body).hexdigest() != pin["sha256"]:
            raise VerificationError(f"P5 staged Git blob differs from pin: {relative}")
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
            f"P5 runner staging exposes forbidden bytes: {forbidden_exposed}"
        )
    return rows


def _run_one_isolated_replay(
    staging: Path, julia_executable: Path, depot: Path, run_root: Path,
    fixture: Mapping[str, Any], abi_mounts: Sequence[tuple[Path, str]],
    candidate_id: str,
) -> bytes:
    for executable in ("bwrap", "systemd-run", "systemctl"):
        if shutil.which(executable) is None:
            raise IndeterminateReplay(f"{executable} is required for P5 formal replay")
    cgroup = subprocess.run(
        ["stat", "-fc", "%T", "/sys/fs/cgroup"], capture_output=True, check=False,
    )
    if cgroup.stdout.strip() != b"cgroup2fs":
        raise IndeterminateReplay("P5 formal replay requires cgroup v2")
    scratch = run_root / "scratch"
    for relative in ("depot", "home", "tmp"):
        (scratch / relative).mkdir(parents=True, exist_ok=False)
    verified_julia = Path(julia_executable).resolve()
    runtime_root = verified_julia.parent.parent
    if verified_julia != (runtime_root / "bin" / "julia").resolve():
        raise IndeterminateReplay("P5 Julia executable differs from runtime_root/bin/julia")
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
    exponent = CANDIDATE_EXPONENTS[candidate_id]
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
        "/repo/majorana_certificate_p5/majorana_p5_runner.jl",
        "/repo/majorana_certificate_p5_fixture.json",
        "/repo/majorana_certificate_p4_fixture.json",
        "/repo/majorana_certificate_p3_fixture.json",
        "/repo/majorana_certificate_p2_fixture.json",
        str(exponent),
    ))
    host = fixture["host_supervisor_caps"]
    unit = f"majorana-p5-{candidate_id.lower()}-{uuid.uuid4().hex}"
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
            raise IndeterminateReplay("P5 scope termination failure") from error
    for reader in readers:
        reader.join(timeout=10)
    stdout, stderr = b"".join(stdout_chunks), b"".join(stderr_chunks)
    if reason:
        raise IndeterminateReplay(f"P5 host resource abort: {reason}")
    if stdout_exceeded.is_set() or len(stdout) > host["maximum_stdout_bytes"]:
        raise IndeterminateReplay("P5 isolated replay exceeded stdout cap")
    if stderr_exceeded.is_set() or len(stderr) > host["maximum_stderr_bytes"]:
        raise IndeterminateReplay("P5 isolated replay exceeded stderr cap")
    if returncode != 0 or stderr:
        diagnostic = stderr.decode("utf-8", errors="replace")[-4000:]
        raise IndeterminateReplay(
            f"P5 {candidate_id} isolated replay failed ({returncode}): {diagnostic}"
        )
    return stdout


def fresh_replay(
    precommit_commit: str, julia_executable: Path, depot: Path,
    base: Path = BASE,
) -> dict[str, Any]:
    base = Path(base)
    fixture = validate_fixture(load_json(base / FIXTURE_NAME), base)
    runtime_lock = P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), fixture, runtime_lock)
    # Shape/pins only: result-bearing outer rows are not opened here.
    contract = validate_precommit_contract(
        load_json(base / PRECOMMIT_CONTRACT_NAME), base,
        verify_source_files=False,
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
        raise IndeterminateReplay("P5 host ABI/locale differs from P3 custody")

    with tempfile.TemporaryDirectory(prefix="majorana-p5-formal-") as temporary:
        root = Path(temporary)
        environment_snapshot = root / "environment-snapshot"
        environment_snapshot.mkdir()
        abi_mounts, abi_snapshot = P3._host_abi_mounts_and_custody(
            environment_snapshot,
        )
        if abi_snapshot != abi_before:
            raise IndeterminateReplay("P5 host environment changed while taking snapshot")
        environment_snapshot_digest = P0._tree_digest(environment_snapshot)
        staging = root / "runner-staging"
        staging.mkdir()
        runner_manifest = _stage_runner_tree(
            repo, base_relative, precommit_commit, contract, staging,
        )
        staging_before = P0._tree_digest(staging)

        # All four processes finish before any independent scientific oracle,
        # P3/P4 result, or D0 report is opened.  Candidate pair equality is
        # established on raw stdout bytes, not merely parsed JSON values.
        outputs: dict[str, list[bytes]] = {candidate: [] for candidate in CANDIDATE_ORDER}
        parsed: dict[str, list[Mapping[str, Any]]] = {
            candidate: [] for candidate in CANDIDATE_ORDER
        }
        process_bindings: list[dict[str, Any]] = []
        process_index = 0
        for candidate_id in CANDIDATE_ORDER:
            for ordinal in (1, 2):
                process_index += 1
                run_root = root / f"run-{process_index}-{candidate_id.lower()}-{ordinal}"
                run_root.mkdir()
                output = _run_one_isolated_replay(
                    staging, Path(julia_executable), depot, run_root, fixture,
                    abi_mounts, candidate_id,
                )
                raw = P3.strict_json_loads(
                    output,
                    source=f"P5 {candidate_id} fresh replay {ordinal} stdout",
                )
                if output != canonical_bytes(raw) + b"\n":
                    raise VerificationError("P5 Julia stdout is not canonical JSON plus newline")
                outputs[candidate_id].append(output)
                parsed[candidate_id].append(raw)
                process_bindings.append({
                    "candidate_id": candidate_id,
                    "fresh_replay_ordinal": ordinal,
                    "global_process_ordinal": process_index,
                    "stdout_sha256": hashlib.sha256(output).hexdigest(),
                    "fresh_writable_scratch_and_depot_prefix": True,
                    "state_cache_or_checkpoint_shared_with_another_process": False,
                })

        for candidate_id in CANDIDATE_ORDER:
            if outputs[candidate_id][0] != outputs[candidate_id][1]:
                raise VerificationError(
                    f"two fresh {candidate_id} Julia stdout byte streams differ"
                )
        raw_map: dict[str, Mapping[str, Any]] = {}
        for candidate_id in CANDIDATE_ORDER:
            raw = validate_raw_witness(
                parsed[candidate_id][0], fixture, runtime_lock,
                candidate_id, base,
            )
            if parsed[candidate_id][1] != raw:
                raise VerificationError(
                    f"second {candidate_id} raw differs despite transcript equality"
                )
            raw_map[candidate_id] = raw

        # This is the first point at which result-bearing P3/P4 bytes and the
        # non-authoritative D0 report may be read.
        composed = _compose_authoritative_witness(raw_map, fixture, policy, base)
        validate_precommit_contract(
            load_json(base / PRECOMMIT_CONTRACT_NAME), base,
            verify_source_files=True,
        )
        outer_manifest = _outer_commit_closure(
            repo, base_relative, precommit_commit, contract, base,
        )
        if P0._tree_digest(staging) != staging_before:
            raise VerificationError("P5 runner staging was modified")
        if P0._tree_digest(environment_snapshot) != environment_snapshot_digest:
            raise IndeterminateReplay("P5 captured environment changed during replay")

    if P0._verify_depot_custody(depot, runtime_lock) != depot_before:
        raise VerificationError("P5 replay modified pinned depot custody")
    _mounts_after, abi_after = P3._host_abi_mounts_and_custody()
    if abi_after != abi_before:
        raise IndeterminateReplay("P5 host environment changed during replay")
    if P2._run_git(repo, "rev-parse", "HEAD").stdout.decode().strip() != precommit_commit:
        raise VerificationError("HEAD changed during P5 replay")
    if P2._run_git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout:
        raise VerificationError("worktree changed during P5 replay")

    transcripts = {
        candidate_id: [hashlib.sha256(output).hexdigest() for output in outputs[candidate_id]]
        for candidate_id in CANDIDATE_ORDER
    }
    raw_hashes = {
        candidate_id: canonical_sha256(raw_map[candidate_id])
        for candidate_id in CANDIDATE_ORDER
    }
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
            "ten_file_result_blind_runner_stage_plus_runtime_read_only_depot_"
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
        "fresh_process_count": 4,
        "candidate_process_order": list(CANDIDATE_ORDER),
        "two_fresh_processes_per_candidate": True,
        "each_process_executes_step1_then_its_candidate_step2_same_process": True,
        "cross_candidate_state_cache_checkpoint_or_writable_scratch_shared": False,
        "candidate_process_bindings": process_bindings,
        "pair_stdout_byte_identical_by_candidate": {
            candidate_id: True for candidate_id in CANDIDATE_ORDER
        },
        "raw_transcript_sha256_in_order_by_candidate": transcripts,
        "raw_witness_sha256_by_candidate": raw_hashes,
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
        raise SchemaError("P5 precommit commit must be a full lowercase Git SHA-1")
    base = Path(base)
    repo, base_relative = P2._repo_and_base_relative(base)
    resolved = P2._run_git(repo, "rev-parse", commit).stdout.decode().strip()
    object_type = P2._run_git(repo, "cat-file", "-t", commit).stdout.decode().strip()
    if resolved != commit or object_type != "commit":
        raise VerificationError("P5 precommit commit does not resolve exactly")
    parent = P2._run_git(repo, "show", "-s", "--format=%P", commit).stdout.decode().strip()
    if parent != REQUIRED_PARENT_COMMIT:
        raise VerificationError("P5 replay commit lacks the frozen direct parent")
    _verify_precommit_changed_path_allowlist(repo, base_relative, commit)
    if P2._run_git(
        repo, "merge-base", "--is-ancestor", commit, "HEAD", check=False,
    ).returncode != 0:
        raise VerificationError("P5 replay commit is not an ancestor of current HEAD")
    remote_contains = P2._run_git(repo, "branch", "-r", "--contains", commit).stdout.decode()
    if "origin/" not in remote_contains:
        raise VerificationError("P5 replay commit was not pushed to an origin remote branch")
    outer = _outer_commit_closure(repo, base_relative, commit, contract, base)
    with tempfile.TemporaryDirectory(prefix="majorana-p5-evidence-") as temporary:
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
    "fresh_process_count", "candidate_process_order",
    "two_fresh_processes_per_candidate",
    "each_process_executes_step1_then_its_candidate_step2_same_process",
    "cross_candidate_state_cache_checkpoint_or_writable_scratch_shared",
    "candidate_process_bindings", "pair_stdout_byte_identical_by_candidate",
    "raw_transcript_sha256_in_order_by_candidate",
    "raw_witness_sha256_by_candidate", "canonical_witness_sha256", "witness",
    "terminal_branch", "status",
)


def _validate_replay_package(
    package: Any, base: Path = BASE,
) -> Mapping[str, Any]:
    base = Path(base)
    if not isinstance(package, dict):
        raise SchemaError("P5 replay package must be an object")
    require_exact_keys(package, _PACKAGE_KEYS, "P5 replay package")
    if package["schema_version"] != 1 or package["package_type"] != PACKAGE_TYPE:
        raise SchemaError("unexpected P5 replay package identity")
    fixture = validate_fixture(load_json(base / FIXTURE_NAME), base)
    runtime_lock = P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), fixture, runtime_lock)
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
        raise VerificationError("P5 replay terminal branch/status mismatch")
    if (
        package["fresh_process_count"] != 4
        or package["candidate_process_order"] != list(CANDIDATE_ORDER)
        or package["two_fresh_processes_per_candidate"] is not True
        or package["each_process_executes_step1_then_its_candidate_step2_same_process"]
        is not True
        or package["cross_candidate_state_cache_checkpoint_or_writable_scratch_shared"]
        is not False
        or package["pair_stdout_byte_identical_by_candidate"]
        != {candidate_id: True for candidate_id in CANDIDATE_ORDER}
    ):
        raise VerificationError("P5 replay freshness/isolation evidence mismatch")
    raw_map = witness["raw_witnesses_by_candidate"]
    expected_transcripts: dict[str, list[str]] = {}
    expected_raw_hashes: dict[str, str] = {}
    expected_bindings: list[dict[str, Any]] = []
    global_ordinal = 0
    for candidate_id in CANDIDATE_ORDER:
        raw_bytes = canonical_bytes(raw_map[candidate_id])
        raw_hash = hashlib.sha256(raw_bytes).hexdigest()
        transcript = hashlib.sha256(raw_bytes + b"\n").hexdigest()
        expected_raw_hashes[candidate_id] = raw_hash
        expected_transcripts[candidate_id] = [transcript, transcript]
        for fresh_ordinal in (1, 2):
            global_ordinal += 1
            expected_bindings.append({
                "candidate_id": candidate_id,
                "fresh_replay_ordinal": fresh_ordinal,
                "global_process_ordinal": global_ordinal,
                "stdout_sha256": transcript,
                "fresh_writable_scratch_and_depot_prefix": True,
                "state_cache_or_checkpoint_shared_with_another_process": False,
            })
    if package["raw_witness_sha256_by_candidate"] != expected_raw_hashes:
        raise VerificationError("P5 raw witness digest map mismatch")
    if package["raw_transcript_sha256_in_order_by_candidate"] != expected_transcripts:
        raise VerificationError("P5 raw transcript digest map mismatch")
    if package["candidate_process_bindings"] != expected_bindings:
        raise VerificationError("P5 candidate process/ordinal binding mismatch")
    if package["canonical_witness_sha256"] != canonical_sha256(witness):
        raise VerificationError("P5 composed witness digest mismatch")
    if package["precommit_contract_sha256"] != file_sha256(base / PRECOMMIT_CONTRACT_NAME):
        raise VerificationError("P5 replay precommit contract digest mismatch")
    if (
        package["network_isolation"] != "bubblewrap_unshared_network_namespace"
        or package["PID_isolation"] != "bubblewrap_unshared_PID_namespace"
        or package["mount_isolation"] != (
            "ten_file_result_blind_runner_stage_plus_runtime_read_only_depot_"
            "fresh_scratch_18_file_host_environment_and_private_proc_dev_only"
        )
    ):
        raise VerificationError("P5 replay isolation declaration mismatch")
    expected_host = {
        "cgroup_version": 2,
        "supervisor": "systemd_user_scope",
        "MemoryMax_bytes": fixture["host_supervisor_caps"]["MemoryMax_bytes"],
        "MemorySwapMax_bytes": fixture["host_supervisor_caps"]["MemorySwapMax_bytes"],
        "RuntimeMaxSec": fixture["host_supervisor_caps"]["RuntimeMaxSec"],
        "observed_runtime_or_memory_peak_in_canonical_package": False,
    }
    if package["host_resource_enforcement"] != expected_host:
        raise VerificationError("P5 replay host resource declaration mismatch")
    environment = P3._validate_environment_manifest(
        package["host_abi_and_locale_custody"]
    )
    p4_fixture = load_json(base / P4_FIXTURE_NAME)
    if (
        package["host_abi_and_locale_custody_sha256"] != canonical_sha256(environment)
        or package["host_abi_and_locale_custody_sha256"]
        != p4_fixture["required_parent_P3"]["host_abi_and_locale_custody_sha256"]
    ):
        raise VerificationError("P5 replay environment custody mismatch")
    P2._validate_recorded_depot_custody(package["depot_custody"], runtime_lock)
    outer, runner, tree_digest = _committed_replay_evidence(
        package["precommit_commit_sha"], precommit, base,
    )
    if (
        package["outer_custody_manifest"] != outer
        or package["outer_custody_manifest_sha256"] != canonical_sha256(outer)
    ):
        raise VerificationError("P5 outer custody evidence mismatch")
    if (
        package["runner_staging_manifest"] != runner
        or package["runner_staging_manifest_sha256"] != canonical_sha256(runner)
        or package["runner_staging_tree_sha256"] != tree_digest
    ):
        raise VerificationError("P5 runner staging evidence mismatch")
    for field in (
        "precommit_contract_sha256", "outer_custody_manifest_sha256",
        "runner_staging_manifest_sha256", "runner_staging_tree_sha256",
        "host_abi_and_locale_custody_sha256", "canonical_witness_sha256",
    ):
        require_sha256(package[field], f"P5 replay {field}")
    for candidate_id in CANDIDATE_ORDER:
        require_sha256(
            package["raw_witness_sha256_by_candidate"][candidate_id],
            f"P5 {candidate_id} raw witness hash",
        )
    return package


COMMON_CERTIFICATE_CLAIMS = (
    "fixed_L8_P3_2^-34_step1_then_conditional_K36_or_K37_step2_execution",
    "four_fresh_network_isolated_cgroup_limited_processes_two_per_candidate",
    "byte_identical_stdout_within_each_candidate_pair",
    "independent_integer_binary64_RNE_replay_through_each_recorded_candidate_prefix",
    "ordered_ComplexF64_times_Complex_Int64_signed_zero_regression_guard",
    "ten_file_result_blind_runner_stage_and_host_environment_custody",
)

COMPLETED_CANDIDATE_CLAIMS = (
    "complete_fieldwise_conformance_of_each_candidate_step1_to_certified_P3",
    "P3_E1_inherited_exactly_once_per_completed_candidate",
    "P4_E12_and_P4_step2_numeric_error_not_inherited",
    "candidate_step2_product_merge_and_executed_drop_local_defect_ledgers",
    "strict_candidate_local_one_over_400000_comparisons",
    "strict_conditional_cumulative_one_over_200000_comparisons",
    "exact_dyadic_candidate_Neel_centers_and_conditional_two_step_intervals",
)

SELECTED_CANDIDATE_CLAIMS = (
    "all_candidates_complete_before_pre_registered_K36_then_K37_selection",
    "selected_candidate_passes_both_strict_allocations",
)

NO_SELECTION_CLAIMS = (
    "all_candidates_complete_before_pre_registered_K36_then_K37_no_selection",
    "neither_fixed_candidate_passes_both_required_allocations",
)

CAP_ONLY_CLAIMS = (
    "required_candidate_pair_reproduces_the_same_first_deterministic_policy_cap",
    "policy_cap_has_resource_guard_authority_only",
    "no_candidate_selection_or_completed_allocation_claim",
    "P3_E1_not_inherited_on_the_cap_only_branch",
)

FAILED_CONFORMANCE_CLAIMS = (
    "at_least_one_complete_step1_projection_failed_certified_P3_fieldwise_conformance",
    "P3_E1_not_inherited_after_conformance_failure",
    "no_candidate_selection_or_completed_allocation_claim",
    "failure_branch_has_no_scientific_bound_authority",
)

# Public maximum-positive claim vocabulary; materialization narrows this tuple
# for no-selection and cap-only terminal branches below.
CERTIFICATE_CLAIMS = (
    *COMMON_CERTIFICATE_CLAIMS,
    *COMPLETED_CANDIDATE_CLAIMS,
    *SELECTED_CANDIDATE_CLAIMS,
)

CERTIFICATE_EXCLUSIONS = (
    "uniform_2^-36_or_2^-37_threshold_across_both_steps",
    "budget_constrained_drop",
    "global_coefficientwise_interval_state",
    "equality_of_executed_and_exact_arithmetic_threshold_drop_sets",
    "raw_unfused_constituent_threshold_path",
    "cancellation_correlation_or_cross_candidate_error_credit",
    "general_threshold_method_or_actual_simulation_error_no_go",
    "double_occupancy",
    "remaining_98_mapped_steps_or_full_R100",
    "product_formula_to_exact_Hubbard_error_or_exact_time_evolution",
    "physical_reference_qualification_or_READY",
    "D0_resource_observations_as_scientific_error_or_selection_evidence",
    "host_runtime_RSS_paths_timestamps_inodes_or_process_identifiers",
)


_RESULT_KEYS = (
    "schema_version", "contract_type", "precommit_commit_sha",
    "precommit_contract_sha256", "replay_package_sha256",
    "outer_custody_manifest_sha256", "runner_staging_manifest_sha256",
    "runner_staging_tree_sha256", "depot_custody",
    "host_abi_and_locale_custody", "host_abi_and_locale_custody_sha256",
    "network_isolation", "PID_isolation", "mount_isolation",
    "host_resource_enforcement", "fresh_process_count",
    "candidate_process_order", "two_fresh_processes_per_candidate",
    "each_process_executes_step1_then_its_candidate_step2_same_process",
    "cross_candidate_state_cache_checkpoint_or_writable_scratch_shared",
    "candidate_process_bindings", "pair_stdout_byte_identical_by_candidate",
    "raw_transcript_sha256_in_order_by_candidate",
    "raw_witness_sha256_by_candidate", "canonical_witness_sha256", "witness",
    "terminal_branch", "status", "scope",
)


def _certificate_authority_and_claims(
    package: Mapping[str, Any],
) -> tuple[str, list[str]]:
    branch = package["terminal_branch"]
    selected = package["witness"]["selected_candidate_id"]
    if branch in (
        "K36_SELECTED_AFTER_ALL_CANDIDATES_COMPLETE",
        (
            "K37_SELECTED_AFTER_K36_NOT_WITHIN_BOTH_ALLOCATIONS_AND_ALL_"
            "CANDIDATES_COMPLETE"
        ),
    ):
        if selected not in CANDIDATE_ORDER:
            raise VerificationError("P5 selected branch lacks its candidate")
        return (
            (
                "fixed_L8_certified_P3_2^-34_step1_then_selected_conditional_"
                f"{selected}_step2_operator_and_checkerboard_Neel_enclosure_only"
            ),
            list(CERTIFICATE_CLAIMS),
        )
    if branch == "NO_CANDIDATE_WITHIN_BOTH_ALLOCATIONS_AFTER_ALL_CANDIDATES_COMPLETE":
        if selected is not None:
            raise VerificationError("P5 no-selection branch names a candidate")
        return (
            (
                "completed_fixed_K36_and_K37_conditional_bounds_and_no_"
                "selection_only_not_a_general_threshold_or_simulation_no_go"
            ),
            [
                *COMMON_CERTIFICATE_CLAIMS,
                *COMPLETED_CANDIDATE_CLAIMS,
                *NO_SELECTION_CLAIMS,
            ],
        )
    if branch == "REQUIRED_CANDIDATE_DETERMINISTIC_POLICY_CAP_EXCEEDED":
        if selected is not None:
            raise VerificationError("P5 cap-only branch names a candidate")
        return (
            (
                "candidate_specific_deterministic_resource_guard_event_only_"
                "without_winner_conformance_inheritance_or_completed_allocation_authority"
            ),
            [*COMMON_CERTIFICATE_CLAIMS, *CAP_ONLY_CLAIMS],
        )
    if branch == "FAILED_P3_POST_REPLAY_CONFORMANCE":
        if selected is not None:
            raise VerificationError("P5 conformance-failure branch names a candidate")
        return (
            "none_P3_post_replay_fieldwise_conformance_failed_without_E1_inheritance",
            [*COMMON_CERTIFICATE_CLAIMS, *FAILED_CONFORMANCE_CLAIMS],
        )
    raise VerificationError("P5 terminal branch cannot be materialized as a certificate")


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
        "fresh_process_count": package["fresh_process_count"],
        "candidate_process_order": package["candidate_process_order"],
        "two_fresh_processes_per_candidate": package[
            "two_fresh_processes_per_candidate"
        ],
        "each_process_executes_step1_then_its_candidate_step2_same_process": package[
            "each_process_executes_step1_then_its_candidate_step2_same_process"
        ],
        "cross_candidate_state_cache_checkpoint_or_writable_scratch_shared": package[
            "cross_candidate_state_cache_checkpoint_or_writable_scratch_shared"
        ],
        "candidate_process_bindings": package["candidate_process_bindings"],
        "pair_stdout_byte_identical_by_candidate": package[
            "pair_stdout_byte_identical_by_candidate"
        ],
        "raw_transcript_sha256_in_order_by_candidate": package[
            "raw_transcript_sha256_in_order_by_candidate"
        ],
        "raw_witness_sha256_by_candidate": package[
            "raw_witness_sha256_by_candidate"
        ],
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
        "selected_candidate_id": package["witness"]["selected_candidate_id"],
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
        "D0_has_scientific_or_selection_authority": False,
        "parent_P4_result_contract_sha256": file_sha256(
            base / P4_RESULT_CONTRACT_NAME
        ),
        "parent_P4_certificate_sha256": file_sha256(base / P4_CERTIFICATE_NAME),
        "P4_numeric_E12_or_step2_error_inherited": False,
        "parent_P3_result_contract_sha256": file_sha256(
            base / P3_RESULT_CONTRACT_NAME
        ),
        "parent_P3_certificate_sha256": file_sha256(base / P3_CERTIFICATE_NAME),
        "raw_witness_sha256_by_candidate": package[
            "raw_witness_sha256_by_candidate"
        ],
        "canonical_witness_sha256": package["canonical_witness_sha256"],
        "candidate_result_sha256_by_candidate": {
            row["candidate_id"]: canonical_sha256(row)
            for row in package["witness"]["candidate_results"]
        },
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
        raise VerificationError("P5 result outer custody digest mismatch")
    if result["runner_staging_manifest_sha256"] != canonical_sha256(runner):
        raise VerificationError("P5 result runner staging digest mismatch")
    if result["runner_staging_tree_sha256"] != tree_digest:
        raise VerificationError("P5 result runner staging tree digest mismatch")
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
        "fresh_process_count": result["fresh_process_count"],
        "candidate_process_order": result["candidate_process_order"],
        "two_fresh_processes_per_candidate": result[
            "two_fresh_processes_per_candidate"
        ],
        "each_process_executes_step1_then_its_candidate_step2_same_process": result[
            "each_process_executes_step1_then_its_candidate_step2_same_process"
        ],
        "cross_candidate_state_cache_checkpoint_or_writable_scratch_shared": result[
            "cross_candidate_state_cache_checkpoint_or_writable_scratch_shared"
        ],
        "candidate_process_bindings": result["candidate_process_bindings"],
        "pair_stdout_byte_identical_by_candidate": result[
            "pair_stdout_byte_identical_by_candidate"
        ],
        "raw_transcript_sha256_in_order_by_candidate": result[
            "raw_transcript_sha256_in_order_by_candidate"
        ],
        "raw_witness_sha256_by_candidate": result[
            "raw_witness_sha256_by_candidate"
        ],
        "canonical_witness_sha256": result["canonical_witness_sha256"],
        "witness": result["witness"],
        "terminal_branch": result["terminal_branch"],
        "status": result["status"],
    }


def verify_final(base: Path = BASE) -> dict[str, Any]:
    base = Path(base)
    fixture = validate_fixture(load_json(base / FIXTURE_NAME), base)
    runtime_lock = P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), fixture, runtime_lock)
    precommit = validate_precommit_contract(
        load_json(base / PRECOMMIT_CONTRACT_NAME), base,
    )
    result_path = base / RESULT_CONTRACT_NAME
    certificate_path = base / CERTIFICATE_NAME
    result = _load_persisted_json(result_path, base)
    certificate = _load_persisted_json(certificate_path, base)
    if not isinstance(result, dict):
        raise SchemaError("P5 result contract must be an object")
    require_exact_keys(result, _RESULT_KEYS, "P5 result contract")
    if result["schema_version"] != 1 or result["contract_type"] != RESULT_CONTRACT_TYPE:
        raise SchemaError("unexpected P5 result contract identity")
    if result_path.read_bytes() != canonical_bytes(result) + b"\n":
        raise VerificationError("P5 result contract is not canonical JSON plus newline")
    package = _package_from_result(result, precommit, base)
    _validate_replay_package(package, base)
    if result["replay_package_sha256"] != hashlib.sha256(
        canonical_bytes(package) + b"\n"
    ).hexdigest():
        raise VerificationError("P5 replay package digest is not reconstructible")
    if result["scope"] != result["witness"]["scope"]:
        raise VerificationError("P5 result scope mismatch")
    expected_contract, expected_certificate = materialize_result(package, base)
    if result != expected_contract:
        raise VerificationError("P5 result contract content mismatch")
    if certificate_path.read_bytes() != canonical_bytes(certificate) + b"\n":
        raise VerificationError("P5 certificate is not canonical JSON plus newline")
    if certificate != expected_certificate:
        raise VerificationError("P5 certificate content mismatch")
    return {
        "status": result["status"],
        "terminal_branch": result["terminal_branch"],
        "selected_candidate_id": result["witness"]["selected_candidate_id"],
        "precommit_commit_sha": result["precommit_commit_sha"],
        "raw_witness_sha256_by_candidate": result[
            "raw_witness_sha256_by_candidate"
        ],
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
            "selected_candidate_id": package["witness"]["selected_candidate_id"],
            "raw_witness_sha256_by_candidate": package[
                "raw_witness_sha256_by_candidate"
            ],
            "canonical_witness_sha256": package["canonical_witness_sha256"],
            "raw_transcript_sha256_in_order_by_candidate": package[
                "raw_transcript_sha256_in_order_by_candidate"
            ],
        }
    elif args.materialize_result:
        if not all((args.replay_output, args.contract_output, args.certificate_output)):
            parser.error("materialization requires replay, contract, and certificate paths")
        package = _strict_persisted_json_loads(
            args.replay_output.read_bytes(), source="P5 replay package",
            maximum_bytes=_persisted_result_byte_cap(BASE),
        )
        contract, certificate = materialize_result(package)
        _write_canonical_json(args.contract_output, contract)
        _write_canonical_json(args.certificate_output, certificate)
        summary = {
            "status": contract["status"],
            "terminal_branch": contract["terminal_branch"],
            "selected_candidate_id": contract["witness"]["selected_candidate_id"],
            "result_contract_sha256": file_sha256(args.contract_output),
            "certificate_sha256": file_sha256(args.certificate_output),
        }
    else:
        summary = verify_final()
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
