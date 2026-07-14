#!/usr/bin/env python3
"""Validate the non-admitting Track B live-binding inventory.

A successful check means only that the frozen missing-binding inventory is
complete for its declared scope, responsibility classes have not drifted, and
the public supporting material still has the recorded bytes.  This checker has
no admission mode and cannot authorize capture, generation, review, unblinding,
scoring, deployment, or a scientific claim.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Callable


LEDGER_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json"
)
CONTRACT_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
)
LEDGER_SCHEMA = "agent_bridge.biocortex_ab_track_b_live_binding_ledger.v0"
CONTRACT_SCHEMA = "agent_bridge.biocortex_ab_track_b_real_run_admission.v0"
LEDGER_ID = "biocortex_ab_track_b_live_binding_ledger_20260714"
CONTRACT_ID = "biocortex_ab_track_b_real_run_admission_20260713"
BASELINE_COMMIT = "f19ec1a813ceb2d29be0a74a430293d8b998a574"
CONTRACT_SHA256 = "1508c0c990ccf9ce26fa0eb524194bb587816cc78d4546236c8d9c00dd3b306e"
CLASSIFICATION_CATALOG_SHA256 = (
    "a0696a1cc3461e96c8ce1b048fd626faf7ccac2203d36c89611b8f09ba33aef3"
)
LOCAL_EVIDENCE_CATALOG_SHA256 = (
    "9545cf504a4e7be20d1cb5170ecbdef64973a786e6d187b7c8cd6c7fc872d992"
)
UNSET_BLOCKS_REAL_RUN = "UNSET_BLOCKS_REAL_RUN"
AMBIENT_UNSET = "UNSET"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

EXPECTED_TOP_LEVEL_KEYS = {
    "admission",
    "authority",
    "baseline_commit",
    "bindings",
    "classification_catalog_sha256",
    "contract",
    "coverage",
    "date",
    "ledger_id",
    "local_evidence",
    "local_evidence_catalog_sha256",
    "local_fill_policy",
    "schema",
    "stage_obligations",
    "stages",
}
EXPECTED_BINDING_KEYS = {
    "binding_evidence",
    "binding_path",
    "binding_satisfied",
    "local_fill_rule",
    "owner_class",
    "required_stage",
    "unlocks_side_effect",
    "value_kind",
}
EXPECTED_AUTHORITY_KEYS = {
    "agent_bridge_db_write",
    "agent_bridge_retrieval_execution",
    "biocortex_runtime_influence",
    "capture",
    "deployment",
    "generation",
    "production_promotion",
    "real_review",
    "scientific_claim",
    "scoring",
    "unblinding",
}
EXPECTED_AMBIENT_UNSET_PATHS = {
    "reference_condition.ambient_inputs.required_effective_environment."
    "AGENT_BRIDGE_MEMORY_CLASS_QUOTA",
    "reference_condition.ambient_inputs.required_effective_environment."
    "AGENT_BRIDGE_MEMORY_SEARCH_EXCLUDE_KINDS",
}
EXPECTED_POST_GENERATION_PATHS = {
    "review_and_blinding.blind_map_sha256",
    "review_and_blinding.blind_packet_sha256",
    "review_and_blinding.capture_sha256",
    "review_and_blinding.generation_sha256",
}
EXPECTED_BLOCKED_LOCAL_PATHS = {
    "candidate_condition.candidate_context_builder_sha256",
    "latency.total_expected_units",
    "power_and_estimator.required_primary_case_count",
    "storage.arm_builder_manifest_sha256",
}
EXPECTED_OWNER_COUNTS = {
    "custodian_private": 25,
    "local_deterministic": 27,
    "owner_policy": 23,
    "runtime_capture": 16,
}
EXPECTED_FILL_COUNTS = {
    "BLOCKED_UNTIL_UPSTREAM_BINDING": 4,
    "EXACT_COMMITTED_ARTIFACT_ONLY": 23,
    "PROHIBITED_LOCAL_SYNTHESIS": 64,
}
EXPECTED_SECTION_COUNTS = {
    "candidate_condition": 1,
    "context_and_result": 6,
    "generation": 6,
    "latency": 9,
    "power_and_estimator": 7,
    "reference_condition": 9,
    "review_and_blinding": 16,
    "sampling": 19,
    "storage": 11,
    "truth_inputs": 7,
}
EXPECTED_DRIFT_PATHS = [
    "crates/bridge/src/mcp_tools.rs",
    "crates/store/src/lib.rs",
    "crates/store/src/sqlite.rs",
]
EXPECTED_STAGE_OBLIGATIONS = [
    {
        "binding_field_present": False,
        "obligation": "both_command_request_raw_response_and_receipt_chains",
        "owner_class": "custodian_private",
        "required_stage": "PRE_UNBLIND",
        "status": "DECLARED_SYMBOL_NOT_BINDING_FIELD_BLOCKS",
    },
    {
        "binding_field_present": False,
        "obligation": "both_complete_review_objects",
        "owner_class": "custodian_private",
        "required_stage": "PRE_UNBLIND",
        "status": "DECLARED_SYMBOL_NOT_BINDING_FIELD_BLOCKS",
    },
    {
        "binding_field_present": False,
        "obligation": "contract_scoped_o_excl_score_claim",
        "owner_class": "custodian_private",
        "required_stage": "PRE_UNBLIND",
        "status": "DECLARED_SYMBOL_NOT_BINDING_FIELD_BLOCKS",
    },
    {
        "binding_field_present": False,
        "obligation": "map_bijection_receipt_sha256",
        "owner_class": "custodian_private",
        "required_stage": "POST_GENERATION_PRE_REVIEW",
        "status": "DECLARED_REQUIRED_ARTIFACT_NOT_BINDING_FIELD_BLOCKS",
    },
]


class LedgerError(ValueError):
    pass


def fail(message: str) -> None:
    raise LedgerError(message)


def duplicate_rejector(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("duplicate JSON key")
        result[key] = value
    return result


def canonical_pretty_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        fail(f"value cannot be rendered canonically: {exc}")


def canonical_compact_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        fail(f"value cannot be rendered canonically: {exc}")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_strict_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        fail(f"cannot read {label}: {exc}")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda _: fail("non-finite JSON number"),
            object_pairs_hook=duplicate_rejector,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} root must be an object")
    if raw != canonical_pretty_bytes(value):
        fail(f"{label} must use canonical sorted pretty JSON with one final newline")
    return value, raw


def strict_equal(value: Any, expected: Any) -> bool:
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(value) == set(expected) and all(
            strict_equal(value[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(value) == len(expected) and all(
            strict_equal(left, right) for left, right in zip(value, expected)
        )
    if isinstance(expected, float):
        return math.isfinite(value) and value == expected
    return value == expected


def require_exact(value: Any, expected: Any, path: str) -> None:
    if not strict_equal(value, expected):
        fail(f"{path} drift")


def require_exact_keys(value: Any, expected: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        fail(f"{path} field set drift")
    return value


def require_false(value: Any, path: str) -> None:
    if value is not False:
        fail(f"{path} must remain false")


def walk_scalars(value: Any, path: tuple[str, ...] = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_scalars(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_scalars(child, path + (str(index),))
    else:
        yield ".".join(path), value


def safe_regular_file(root: Path, relative: str) -> Path:
    if (
        not isinstance(relative, str)
        or not relative
        or relative.startswith("/")
        or "\\" in relative
        or "//" in relative
    ):
        fail("supporting-material path is not canonical repo-relative POSIX")
    pure = PurePosixPath(relative)
    if str(pure) != relative or any(part in {"", ".", ".."} for part in pure.parts):
        fail("supporting-material path contains a normalization alias")
    cursor = root
    try:
        for part in pure.parts:
            cursor = cursor / part
            entry = os.lstat(cursor)
            if stat.S_ISLNK(entry.st_mode):
                fail(f"supporting-material path contains a symlink: {relative}")
        final = os.lstat(cursor)
    except OSError as exc:
        fail(f"cannot stat supporting material {relative}: {exc}")
    if not stat.S_ISREG(final.st_mode):
        fail(f"supporting material is not a regular file: {relative}")
    if final.st_nlink != 1:
        fail(f"supporting material has hard-link aliases: {relative}")
    try:
        cursor.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        fail(f"supporting-material path escapes root: {relative}")
    return cursor


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        fail(f"cannot hash {path}: {exc}")
    return digest.hexdigest()


def contract_missing_paths(contract: dict[str, Any]) -> tuple[set[str], set[str]]:
    blocking: set[str] = set()
    literal_unset: set[str] = set()
    for path, value in walk_scalars(contract):
        if value == UNSET_BLOCKS_REAL_RUN:
            blocking.add(path)
        elif value == AMBIENT_UNSET:
            literal_unset.add(path)
    require_exact(literal_unset, EXPECTED_AMBIENT_UNSET_PATHS, "ambient literal UNSET paths")
    require_exact(len(blocking), 89, "contract blocking sentinel count")
    return blocking, literal_unset


def required_unbound_stage_obligations(contract: dict[str, Any]) -> list[dict[str, Any]]:
    stages = require_exact_keys(
        contract.get("stages"),
        {"post_generation_pre_review", "pre_output_admission", "pre_unblind"},
        "contract.stages",
    )
    require_exact(stages["pre_output_admission"]["status"], "BLOCKED", "pre-output status")
    require_exact(
        stages["post_generation_pre_review"]["status"],
        "NOT_REACHED",
        "post-generation status",
    )
    require_exact(stages["pre_unblind"]["status"], "NOT_REACHED", "pre-unblind status")
    post_required = stages["post_generation_pre_review"]["required_artifacts"]
    pre_unblind_required = stages["pre_unblind"]["required_artifacts"]
    require_exact(
        [item for item in post_required if item == "map_bijection_receipt_sha256"],
        ["map_bijection_receipt_sha256"],
        "unbound post-generation obligation",
    )
    require_exact(
        pre_unblind_required,
        [
            "both_complete_review_objects",
            "both_command_request_raw_response_and_receipt_chains",
            "contract_scoped_o_excl_score_claim",
        ],
        "pre-unblind declared obligations",
    )
    return EXPECTED_STAGE_OBLIGATIONS


def validate_contract_structure(
    contract: dict[str, Any],
    raw: bytes,
    root: Path | None,
) -> tuple[set[str], dict[str, int]]:
    require_exact(contract.get("schema"), CONTRACT_SCHEMA, "contract.schema")
    require_exact(contract.get("contract_id"), CONTRACT_ID, "contract.contract_id")
    admission = contract.get("admission")
    if not isinstance(admission, dict):
        fail("contract.admission must be an object")
    require_exact(admission.get("status"), "BLOCKED_FAIL_CLOSED", "contract admission")
    require_false(admission.get("capture_allowed"), "contract capture_allowed")
    require_false(admission.get("real_run_admitted"), "contract real_run_admitted")
    authority = contract.get("authority")
    require_exact_keys(authority, EXPECTED_AUTHORITY_KEYS, "contract.authority")
    for key, value in authority.items():
        require_false(value, f"contract.authority.{key}")

    blocking, ambient = contract_missing_paths(contract)
    all_paths = blocking | ambient
    require_exact(len(all_paths), 91, "live missing scalar binding count")
    section_counts: dict[str, int] = {}
    for path in all_paths:
        section = path.split(".", 1)[0]
        section_counts[section] = section_counts.get(section, 0) + 1
    require_exact(section_counts, EXPECTED_SECTION_COUNTS, "missing paths by section")
    required_unbound_stage_obligations(contract)

    if root is not None:
        rows = contract.get("source_bindings")
        if not isinstance(rows, list) or len(rows) != 11:
            fail("contract source binding count drift")
        drifted: list[str] = []
        matched = 0
        observed: set[str] = set()
        for index, row in enumerate(rows):
            require_exact_keys(
                row,
                {"path", "role", "sha256", "status"},
                f"contract.source_bindings[{index}]",
            )
            relative = row["path"]
            if relative in observed:
                fail("duplicate contract source binding")
            observed.add(relative)
            source = safe_regular_file(root, relative)
            if sha256_file(source) == row["sha256"]:
                matched += 1
            else:
                drifted.append(relative)
        require_exact(matched, 8, "current contract source binding match count")
        require_exact(drifted, EXPECTED_DRIFT_PATHS, "current contract source binding drift")
    require_exact(sha256_bytes(raw), CONTRACT_SHA256, "contract byte identity")
    return all_paths, section_counts


def binding_catalog_bytes(bindings: list[dict[str, Any]]) -> bytes:
    fields = (
        "binding_path",
        "local_fill_rule",
        "owner_class",
        "required_stage",
        "value_kind",
    )
    return canonical_compact_bytes(
        [{key: row[key] for key in fields} for row in bindings]
    )


def validate_bindings(
    ledger: dict[str, Any],
    missing_paths: set[str],
) -> dict[str, int]:
    rows = ledger.get("bindings")
    if not isinstance(rows, list) or len(rows) != 91:
        fail("ledger binding row count drift")
    ordered_paths: list[str] = []
    owner_counts: dict[str, int] = {}
    fill_counts: dict[str, int] = {}
    stage_counts: dict[str, int] = {}
    local_exact_artifact: list[str] = []
    local_blocked: list[str] = []
    for index, row_value in enumerate(rows):
        row = require_exact_keys(row_value, EXPECTED_BINDING_KEYS, f"bindings[{index}]")
        path = row["binding_path"]
        if not isinstance(path, str) or not path:
            fail("binding_path must be a non-empty string")
        ordered_paths.append(path)
        require_false(row["binding_satisfied"], f"{path}.binding_satisfied")
        require_false(row["unlocks_side_effect"], f"{path}.unlocks_side_effect")
        require_exact(row["binding_evidence"], None, f"{path}.binding_evidence")
        expected_kind = "sha256" if path.endswith("_sha256") else "value"
        require_exact(row["value_kind"], expected_kind, f"{path}.value_kind")
        owner = row["owner_class"]
        fill = row["local_fill_rule"]
        stage = row["required_stage"]
        owner_counts[owner] = owner_counts.get(owner, 0) + 1
        fill_counts[fill] = fill_counts.get(fill, 0) + 1
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        if fill == "EXACT_COMMITTED_ARTIFACT_ONLY":
            local_exact_artifact.append(path)
        elif fill == "BLOCKED_UNTIL_UPSTREAM_BINDING":
            local_blocked.append(path)
    if ordered_paths != sorted(ordered_paths):
        fail("binding rows must be sorted by exact dotted path")
    if len(ordered_paths) != len(set(ordered_paths)):
        fail("duplicate binding path")
    require_exact(set(ordered_paths), missing_paths, "ledger/contract missing-path coverage")
    require_exact(owner_counts, EXPECTED_OWNER_COUNTS, "owner-class counts")
    require_exact(fill_counts, EXPECTED_FILL_COUNTS, "local-fill counts")
    require_exact(
        stage_counts,
        {"POST_GENERATION_PRE_REVIEW": 4, "PRE_OUTPUT_ADMISSION": 87},
        "binding stage counts",
    )
    observed_post = {
        row["binding_path"]
        for row in rows
        if row["required_stage"] == "POST_GENERATION_PRE_REVIEW"
    }
    require_exact(observed_post, EXPECTED_POST_GENERATION_PATHS, "post-generation paths")
    require_exact(set(local_blocked), EXPECTED_BLOCKED_LOCAL_PATHS, "blocked local paths")
    catalog_sha = sha256_bytes(binding_catalog_bytes(rows))
    require_exact(catalog_sha, CLASSIFICATION_CATALOG_SHA256, "classification catalog")
    require_exact(
        ledger.get("classification_catalog_sha256"),
        CLASSIFICATION_CATALOG_SHA256,
        "classification_catalog_sha256",
    )

    policy = require_exact_keys(
        ledger.get("local_fill_policy"),
        {
            "blocked_until_upstream_binding_paths",
            "exact_committed_artifact_only_paths",
            "local_evidence_satisfies_binding_count",
            "prohibited_local_synthesis_count",
            "status",
        },
        "local_fill_policy",
    )
    require_exact(
        policy["blocked_until_upstream_binding_paths"],
        sorted(local_blocked),
        "blocked local path projection",
    )
    require_exact(
        policy["exact_committed_artifact_only_paths"],
        sorted(local_exact_artifact),
        "ready local path projection",
    )
    require_exact(policy["local_evidence_satisfies_binding_count"], 0, "local evidence binding count")
    require_exact(policy["prohibited_local_synthesis_count"], 64, "prohibited local synthesis count")
    require_exact(policy["status"], "PLANNED_NOT_BOUND", "local fill policy status")
    return {
        "custodian_private": owner_counts["custodian_private"],
        "local_deterministic": owner_counts["local_deterministic"],
        "owner_policy": owner_counts["owner_policy"],
        "runtime_capture": owner_counts["runtime_capture"],
        "local_exact_artifact": len(local_exact_artifact),
        "local_blocked": len(local_blocked),
    }


def validate_local_evidence(
    ledger: dict[str, Any],
    root: Path | None,
) -> int:
    rows = ledger.get("local_evidence")
    if not isinstance(rows, list) or len(rows) != 24:
        fail("local evidence row count drift")
    paths: list[str] = []
    allowed_statuses = {
        "CONSUMED_PRECEDENT_MECHANISM_ONLY",
        "FROZEN_PROTOCOL_BASELINE_ONLY",
        "LOCAL_SOURCE_IDENTITY_ONLY",
        "PUBLIC_SYNTHETIC_MECHANISM_ONLY",
        "STATIC_BLOCKER_EVIDENCE_ONLY",
    }
    for index, row in enumerate(rows):
        require_exact_keys(
            row,
            {"may_satisfy_live_binding", "path", "role", "sha256", "status"},
            f"local_evidence[{index}]",
        )
        require_false(
            row["may_satisfy_live_binding"],
            f"local_evidence[{index}].may_satisfy_live_binding",
        )
        if not isinstance(row["role"], str) or not row["role"]:
            fail("local evidence role must be non-empty")
        if row["status"] not in allowed_statuses:
            fail("local evidence status drift")
        if not isinstance(row["sha256"], str) or not SHA256_RE.fullmatch(row["sha256"]):
            fail("local evidence SHA-256 invalid")
        paths.append(row["path"])
        if root is not None:
            source = safe_regular_file(root, row["path"])
            require_exact(
                sha256_file(source),
                row["sha256"],
                f"local evidence hash {row['path']}",
            )
    if paths != sorted(paths):
        fail("local evidence paths must be sorted")
    if len(paths) != len(set(paths)):
        fail("duplicate local evidence path")
    evidence_sha = sha256_bytes(canonical_compact_bytes(rows))
    require_exact(evidence_sha, LOCAL_EVIDENCE_CATALOG_SHA256, "local evidence catalog")
    require_exact(
        ledger.get("local_evidence_catalog_sha256"),
        LOCAL_EVIDENCE_CATALOG_SHA256,
        "local_evidence_catalog_sha256",
    )
    return len(rows)


def validate_ledger(
    ledger: dict[str, Any],
    ledger_raw: bytes,
    contract: dict[str, Any],
    contract_raw: bytes,
    root: Path | None,
) -> dict[str, Any]:
    require_exact_keys(ledger, EXPECTED_TOP_LEVEL_KEYS, "ledger")
    require_exact(ledger.get("schema"), LEDGER_SCHEMA, "ledger.schema")
    require_exact(ledger.get("ledger_id"), LEDGER_ID, "ledger.ledger_id")
    require_exact(ledger.get("date"), "2026-07-14", "ledger.date")
    require_exact(ledger.get("baseline_commit"), BASELINE_COMMIT, "baseline_commit")

    admission = require_exact_keys(
        ledger.get("admission"),
        {"capture_allowed", "decision", "real_run_admitted", "side_effects_unlocked"},
        "admission",
    )
    require_exact(admission["decision"], "BLOCKED_FAIL_CLOSED", "admission.decision")
    require_false(admission["capture_allowed"], "admission.capture_allowed")
    require_false(admission["real_run_admitted"], "admission.real_run_admitted")
    require_exact(admission["side_effects_unlocked"], "NONE", "side_effects_unlocked")

    authority = require_exact_keys(ledger.get("authority"), EXPECTED_AUTHORITY_KEYS, "authority")
    for key, value in authority.items():
        require_false(value, f"authority.{key}")

    missing_paths, _ = validate_contract_structure(contract, contract_raw, root)
    binding_metrics = validate_bindings(ledger, missing_paths)

    contract_meta = require_exact_keys(
        ledger.get("contract"),
        {
            "blocker_count",
            "contract_id",
            "current_checker_state",
            "current_source_binding_drift_count",
            "current_source_binding_drift_paths",
            "current_source_binding_match_count",
            "earliest_post_fix_capture_date",
            "path",
            "schema",
            "sha256",
            "source_binding_count",
        },
        "ledger.contract",
    )
    require_exact(
        contract_meta,
        {
            "blocker_count": 12,
            "contract_id": CONTRACT_ID,
            "current_checker_state": "BLOCKED_BY_EXPECTED_SOURCE_DRIFT",
            "current_source_binding_drift_count": 3,
            "current_source_binding_drift_paths": EXPECTED_DRIFT_PATHS,
            "current_source_binding_match_count": 8,
            "earliest_post_fix_capture_date": "2026-07-17",
            "path": CONTRACT_PATH.as_posix(),
            "schema": CONTRACT_SCHEMA,
            "sha256": CONTRACT_SHA256,
            "source_binding_count": 11,
        },
        "ledger.contract",
    )
    require_exact(len(contract.get("blockers", [])), 12, "contract blocker count")
    require_exact(
        contract.get("earliest_post_fix_capture_date"),
        "2026-07-17",
        "contract earliest post-fix capture date",
    )

    coverage = require_exact_keys(
        ledger.get("coverage"),
        {
            "admission_binding_complete",
            "ambient_effective_env_unset_count",
            "classification_mismatch_count",
            "contract_binding_satisfied_count",
            "contract_blocking_sentinel_count",
            "coverage_extra_count",
            "coverage_missing_count",
            "declared_stage_obligation_count",
            "duplicate_binding_count",
            "inventory_complete",
            "inventory_coverage_scope",
            "live_missing_scalar_binding_count",
            "non_sha_binding_count",
            "real_binding_evidence_count",
            "sha256_binding_count",
        },
        "coverage",
    )
    expected_coverage = {
        "admission_binding_complete": False,
        "ambient_effective_env_unset_count": 2,
        "classification_mismatch_count": 0,
        "contract_binding_satisfied_count": 0,
        "contract_blocking_sentinel_count": 89,
        "coverage_extra_count": 0,
        "coverage_missing_count": 0,
        "declared_stage_obligation_count": 4,
        "duplicate_binding_count": 0,
        "inventory_complete": True,
        "inventory_coverage_scope": (
            "CONTRACT_SENTINELS_PLUS_AMBIENT_ENV_AND_DECLARED_STAGE_OBLIGATIONS"
        ),
        "live_missing_scalar_binding_count": 91,
        "non_sha_binding_count": 19,
        "real_binding_evidence_count": 0,
        "sha256_binding_count": 72,
    }
    require_exact(coverage, expected_coverage, "coverage")

    require_exact(
        ledger.get("stage_obligations"),
        EXPECTED_STAGE_OBLIGATIONS,
        "stage_obligations",
    )
    require_exact(
        ledger.get("stages"),
        {
            "post_generation_pre_review": "NOT_REACHED",
            "pre_output_admission": "BLOCKED",
            "pre_unblind": "NOT_REACHED",
        },
        "stages",
    )
    local_evidence_count = validate_local_evidence(ledger, root)
    return {
        **binding_metrics,
        "ledger_sha256": sha256_bytes(ledger_raw),
        "local_evidence_count": local_evidence_count,
    }


def set_path(value: dict[str, Any], path: tuple[Any, ...], replacement: Any) -> None:
    cursor: Any = value
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = replacement


def recompute_classification_hash(ledger: dict[str, Any]) -> None:
    ledger["classification_catalog_sha256"] = sha256_bytes(
        binding_catalog_bytes(ledger["bindings"])
    )


def recompute_evidence_hash(ledger: dict[str, Any]) -> None:
    ledger["local_evidence_catalog_sha256"] = sha256_bytes(
        canonical_compact_bytes(ledger["local_evidence"])
    )


def run_ledger_self_test(
    ledger: dict[str, Any],
    contract: dict[str, Any],
    contract_raw: bytes,
) -> int:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("schema", lambda x: set_path(x, ("schema",), "wrong")),
        ("ledger-id", lambda x: set_path(x, ("ledger_id",), "wrong")),
        ("date", lambda x: set_path(x, ("date",), "2026-07-15")),
        ("baseline", lambda x: set_path(x, ("baseline_commit",), "0" * 40)),
        ("decision", lambda x: set_path(x, ("admission", "decision"), "PASS")),
        ("capture", lambda x: set_path(x, ("admission", "capture_allowed"), True)),
        ("admit", lambda x: set_path(x, ("admission", "real_run_admitted"), True)),
        ("side-effect", lambda x: set_path(x, ("admission", "side_effects_unlocked"), "CAPTURE")),
        ("authority", lambda x: set_path(x, ("authority", "scientific_claim"), True)),
        ("coverage-89", lambda x: set_path(x, ("coverage", "live_missing_scalar_binding_count"), 89)),
        ("ambient-count", lambda x: set_path(x, ("coverage", "ambient_effective_env_unset_count"), 0)),
        ("binding-complete", lambda x: set_path(x, ("coverage", "admission_binding_complete"), True)),
        ("binding-satisfied-count", lambda x: set_path(x, ("coverage", "contract_binding_satisfied_count"), 1)),
        ("real-evidence-count", lambda x: set_path(x, ("coverage", "real_binding_evidence_count"), 1)),
        ("scope", lambda x: set_path(x, ("coverage", "inventory_coverage_scope"), "ALL_BINDINGS")),
        ("remove-binding", lambda x: x["bindings"].pop()),
        ("duplicate-binding", lambda x: x["bindings"].append(copy.deepcopy(x["bindings"][0]))),
        ("binding-satisfied", lambda x: set_path(x, ("bindings", 0, "binding_satisfied"), True)),
        ("binding-evidence", lambda x: set_path(x, ("bindings", 0, "binding_evidence"), {"sha256": "0" * 64})),
        ("binding-unlocks", lambda x: set_path(x, ("bindings", 0, "unlocks_side_effect"), True)),
        ("binding-kind", lambda x: set_path(x, ("bindings", 0, "value_kind"), "sha256" if x["bindings"][0]["value_kind"] == "value" else "value")),
        ("binding-stage", lambda x: set_path(x, ("bindings", 0, "required_stage"), "PRE_UNBLIND")),
        ("blocked-local-remove", lambda x: x["local_fill_policy"]["blocked_until_upstream_binding_paths"].pop()),
        ("ready-local-remove", lambda x: x["local_fill_policy"]["exact_committed_artifact_only_paths"].pop()),
        ("evidence-may-bind", lambda x: set_path(x, ("local_evidence", 0, "may_satisfy_live_binding"), True)),
        ("evidence-hash", lambda x: set_path(x, ("local_evidence", 0, "sha256"), "0" * 64)),
        ("evidence-status", lambda x: set_path(x, ("local_evidence", 0, "status"), "REAL_BINDING")),
        ("evidence-path-traversal", lambda x: set_path(x, ("local_evidence", 0, "path"), "../Cargo.lock")),
        ("remove-stage-obligation", lambda x: x["stage_obligations"].pop()),
        ("stage-status", lambda x: set_path(x, ("stages", "pre_output_admission"), "READY")),
        ("contract-state", lambda x: set_path(x, ("contract", "current_checker_state"), "PASS")),
        ("drift-count", lambda x: set_path(x, ("contract", "current_source_binding_drift_count"), 0)),
        ("full-classification-rebind", full_classification_rebind),
        ("full-evidence-rebind", full_evidence_rebind),
    ]
    rejected = 0
    for label, mutate in mutations:
        trial = copy.deepcopy(ledger)
        mutate(trial)
        raw = canonical_pretty_bytes(trial)
        try:
            validate_ledger(trial, raw, contract, contract_raw, None)
        except LedgerError:
            rejected += 1
        else:
            fail(f"ledger self-test mutation accepted: {label}")
    return rejected


def full_classification_rebind(ledger: dict[str, Any]) -> None:
    row = ledger["bindings"][0]
    row["owner_class"] = "owner_policy"
    row["local_fill_rule"] = "PROHIBITED_LOCAL_SYNTHESIS"
    policy = ledger["local_fill_policy"]
    path = row["binding_path"]
    if path in policy["exact_committed_artifact_only_paths"]:
        policy["exact_committed_artifact_only_paths"].remove(path)
    elif path in policy["blocked_until_upstream_binding_paths"]:
        policy["blocked_until_upstream_binding_paths"].remove(path)
    policy["prohibited_local_synthesis_count"] += 1
    recompute_classification_hash(ledger)


def full_evidence_rebind(ledger: dict[str, Any]) -> None:
    first = ledger["local_evidence"][0]
    second = ledger["local_evidence"][1]
    first["path"] = second["path"] + ".replacement"
    first["sha256"] = second["sha256"]
    first["role"] = second["role"]
    first["status"] = second["status"]
    ledger["local_evidence"].sort(key=lambda row: row["path"])
    recompute_evidence_hash(ledger)


def run_contract_self_test(
    ledger: dict[str, Any],
    ledger_raw: bytes,
    contract: dict[str, Any],
) -> int:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        (
            "resolve-one-placeholder",
            lambda x: set_path(
                x,
                ("candidate_condition", "candidate_context_builder_sha256"),
                "0" * 64,
            ),
        ),
        (
            "resolve-ambient-unset",
            lambda x: set_path(
                x,
                (
                    "reference_condition",
                    "ambient_inputs",
                    "required_effective_environment",
                    "AGENT_BRIDGE_MEMORY_CLASS_QUOTA",
                ),
                "",
            ),
        ),
        (
            "add-new-placeholder",
            lambda x: set_path(x, ("admission", "new_binding"), UNSET_BLOCKS_REAL_RUN),
        ),
        (
            "remove-map-receipt-obligation",
            lambda x: x["stages"]["post_generation_pre_review"]["required_artifacts"].pop(),
        ),
        (
            "advance-contract-stage",
            lambda x: set_path(x, ("stages", "pre_output_admission", "status"), "READY"),
        ),
        (
            "rebind-drifted-source",
            lambda x: set_path(
                x,
                ("source_bindings", 1, "sha256"),
                "65b1cf172217cdde93a80e558fe95d2a69671bb8342bca1f0ed47d0a244b46ce",
            ),
        ),
    ]
    rejected = 0
    for label, mutate in mutations:
        trial = copy.deepcopy(contract)
        mutate(trial)
        raw = canonical_pretty_bytes(trial)
        try:
            validate_ledger(ledger, ledger_raw, trial, raw, None)
        except LedgerError:
            rejected += 1
        else:
            fail(f"contract self-test mutation accepted: {label}")
    return rejected


def render_receipt(
    ledger: dict[str, Any],
    metrics: dict[str, Any],
) -> str:
    coverage = ledger["coverage"]
    rows = [
        ("schema", LEDGER_SCHEMA),
        ("ledger_id", LEDGER_ID),
        ("ledger_sha256", metrics["ledger_sha256"]),
        ("contract_id", CONTRACT_ID),
        ("contract_schema", CONTRACT_SCHEMA),
        ("contract_sha256", CONTRACT_SHA256),
        ("classification_catalog_sha256", CLASSIFICATION_CATALOG_SHA256),
        ("local_evidence_catalog_sha256", LOCAL_EVIDENCE_CATALOG_SHA256),
        ("inventory_coverage_scope", coverage["inventory_coverage_scope"]),
        ("inventory_complete", "true"),
        ("admission_binding_complete", "false"),
        ("decision", "BLOCKED_FAIL_CLOSED"),
        ("real_run_admitted", "false"),
        ("capture_allowed", "false"),
        ("side_effects_unlocked", "NONE"),
        ("authority_true_count", 0),
        ("contract_blocking_sentinel_count", 89),
        ("ambient_effective_env_unset_count", 2),
        ("live_missing_scalar_binding_count", 91),
        ("sha256_binding_count", 72),
        ("non_sha_binding_count", 19),
        ("ledger_row_count", 91),
        ("coverage_missing_count", 0),
        ("coverage_extra_count", 0),
        ("duplicate_binding_count", 0),
        ("classification_mismatch_count", 0),
        ("local_deterministic_count", metrics["local_deterministic"]),
        ("owner_policy_count", metrics["owner_policy"]),
        ("custodian_private_count", metrics["custodian_private"]),
        ("runtime_capture_count", metrics["runtime_capture"]),
        (
            "exact_committed_artifact_only_count",
            metrics["local_exact_artifact"],
        ),
        ("blocked_until_upstream_binding_count", metrics["local_blocked"]),
        ("prohibited_local_synthesis_count", 64),
        ("local_supporting_artifact_count", metrics["local_evidence_count"]),
        ("local_evidence_hash_verified_count", metrics["local_evidence_count"]),
        ("contract_binding_satisfied_count", 0),
        ("real_binding_evidence_count", 0),
        ("external_binding_local_placeholder_count", 0),
        ("pre_output_stage_status", "BLOCKED"),
        ("post_generation_pre_review_stage_status", "NOT_REACHED"),
        ("pre_unblind_stage_status", "NOT_REACHED"),
        ("declared_stage_obligation_count", 4),
        ("all_stage_admission_complete", "false"),
        ("frozen_contract_current_checker_state", "BLOCKED_BY_EXPECTED_SOURCE_DRIFT"),
        ("frozen_contract_source_binding_match_count", 8),
        ("frozen_contract_source_binding_drift_count", 3),
        ("blocker_count", 12),
        ("earliest_post_fix_capture_date", "2026-07-17"),
        ("legacy_confirmatory_reuse_count", 0),
        ("public_runtime_execution", "false"),
    ]
    return "".join(f"{key}\t{value}\n" for key, value in rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    try:
        ledger, ledger_raw = read_strict_json(root / LEDGER_PATH, "ledger")
        contract, contract_raw = read_strict_json(root / CONTRACT_PATH, "contract")
        metrics = validate_ledger(ledger, ledger_raw, contract, contract_raw, root)
        if args.self_test:
            ledger_rejected = run_ledger_self_test(ledger, contract, contract_raw)
            contract_rejected = run_contract_self_test(
                ledger, ledger_raw, contract
            )
            print(
                "SELF_TEST_OK"
                f"\tledger_mutations_rejected={ledger_rejected}"
                f"\tcontract_mutations_rejected={contract_rejected}"
                f"\ttotal_mutations_rejected={ledger_rejected + contract_rejected}"
            )
        else:
            sys.stdout.write(render_receipt(ledger, metrics))
    except LedgerError as exc:
        print(f"Track B live-binding ledger check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
