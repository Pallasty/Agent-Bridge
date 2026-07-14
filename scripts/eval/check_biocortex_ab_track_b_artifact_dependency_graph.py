#!/usr/bin/env python3
"""Validate the planning-only Track B exact-artifact dependency graph.

Passing this checker proves that the frozen 23-path graph is complete and
internally coherent.  It does not prove that any artifact exists, satisfy a
live binding, or authorize capture, generation, review, unblinding, scoring,
deployment, database writes, runtime influence, or a scientific claim.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import heapq
import json
import os
import re
import stat
import sys
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Callable


GRAPH_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"
)
LEDGER_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json"
)
CONTRACT_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
)
GRAPH_SCHEMA = "agent_bridge.biocortex_ab_track_b_artifact_dependency_graph.v0"
GRAPH_ID = "biocortex_ab_track_b_artifact_dependency_graph_20260714"
LEDGER_SCHEMA = "agent_bridge.biocortex_ab_track_b_live_binding_ledger.v0"
LEDGER_ID = "biocortex_ab_track_b_live_binding_ledger_20260714"
BASELINE_COMMIT = "3840fc214118f692d37a54e6abdd46ab192080ad"
LEDGER_SHA256 = "764f063fefe0e516547f9bd1e71417242daf292d57e480ae39b73df8bcda341a"
CONTRACT_SHA256 = "1508c0c990ccf9ce26fa0eb524194bb587816cc78d4546236c8d9c00dd3b306e"
LEDGER_CLASSIFICATION_CATALOG_SHA256 = (
    "a0696a1cc3461e96c8ce1b048fd626faf7ccac2203d36c89611b8f09ba33aef3"
)
DEPENDENCY_CATALOG_SHA256 = (
    "1b9b6382fa43fc84c1954db31622cc18796ad34ac1e408f8624a330e45a85090"
)
EVIDENCE_CATALOG_SHA256 = (
    "179e170205eb0dd7604559844f9ca377e1c79d28b85ea27ebcbbfcd2bcaef130"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LABEL_RE = re.compile(r"^[a-z][a-z0-9_]*$")
REASON_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

EXPECTED_TOP_LEVEL_KEYS = {
    "admission",
    "authority",
    "baseline_commit",
    "date",
    "dependency_catalog_sha256",
    "evidence_catalog",
    "evidence_catalog_sha256",
    "graph_id",
    "nodes",
    "readiness_policy",
    "schema",
    "scope",
    "summary",
}
EXPECTED_NODE_KEYS = {
    "artifact_binding_path",
    "artifact_kind",
    "binding_evidence",
    "binding_satisfied",
    "blocked_upstream_dependencies",
    "committed_artifact_blob_oid",
    "committed_artifact_repo_path",
    "committed_artifact_sha256",
    "evidence_refs",
    "external_dependencies",
    "implementation_status",
    "local_dependencies",
    "primary_readiness_class",
    "public_authoring_eligible",
    "required_stage",
    "unrepresented_upstream_dependencies",
    "unlocks_side_effect",
}
EXPECTED_EVIDENCE_KEYS = {
    "may_satisfy_live_binding",
    "path",
    "reuse_scope",
    "role",
    "sha256",
    "status",
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
EXPECTED_UPSTREAM_PATHS = {
    "candidate_condition.candidate_context_builder_sha256",
    "latency.total_expected_units",
    "power_and_estimator.required_primary_case_count",
    "storage.arm_builder_manifest_sha256",
}
EXPECTED_FIRST_PACK = [
    "review_and_blinding.map_schema_sha256",
    "review_and_blinding.review_command_schema_sha256",
    "sampling.sampling_receipt_schema_sha256",
    "truth_inputs.referent_schema_sha256",
]
CONTROLLING_DEPENDENCY_PRECEDENCE = [
    "BLOCKED_OR_UNREPRESENTED_UPSTREAM",
    "CUSTODIAN_PRIVATE",
    "OWNER_POLICY",
    "RUNTIME_CAPTURE",
    "NO_BLOCKER",
]


class GraphError(ValueError):
    pass


def fail(message: str) -> None:
    raise GraphError(message)


def duplicate_rejector(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            fail("duplicate JSON key")
        value[key] = item
    return value


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
        text = raw.decode("utf-8")
        value = json.loads(text, object_pairs_hook=duplicate_rejector)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"cannot read strict {label}: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    if raw != canonical_pretty_bytes(value):
        fail(f"{label} is not canonical pretty JSON")
    return value, raw


def require_exact(actual: Any, expected: Any, label: str) -> None:
    if canonical_compact_bytes(actual) != canonical_compact_bytes(expected):
        fail(f"{label} drift")


def require_exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        fail(f"{label} keys drift")
    return value


def require_false(value: Any, label: str) -> None:
    if value is not False:
        fail(f"{label} must be false")


def require_int(value: Any, expected: int, label: str) -> None:
    if type(value) is not int or value != expected:
        fail(f"{label} must be integer {expected}")


def require_sorted_unique_strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        fail(f"{label} must be a string list")
    if value != sorted(value) or len(value) != len(set(value)):
        fail(f"{label} must be sorted and unique")
    return value


def require_safe_relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        fail(f"{label} must be a nonempty path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or pure.as_posix() != value or any(
        part in {"", ".", ".."} for part in pure.parts
    ):
        fail(f"{label} is not a canonical relative path")
    return value


def require_regular_unaliased(root: Path, relative: str, label: str) -> Path:
    cursor = root
    for part in PurePosixPath(relative).parts:
        cursor = cursor / part
        try:
            metadata = cursor.lstat()
        except OSError as exc:
            fail(f"cannot stat {label}: {exc}")
        if stat.S_ISLNK(metadata.st_mode):
            fail(f"{label} contains a symlink")
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        fail(f"{label} must be a regular unaliased file")
    return cursor


def validate_source_inputs(
    ledger: dict[str, Any], ledger_raw: bytes, contract_raw: bytes
) -> tuple[dict[str, dict[str, Any]], set[str], set[str]]:
    if sha256_bytes(ledger_raw) != LEDGER_SHA256:
        fail("frozen ledger SHA-256 drift")
    if sha256_bytes(contract_raw) != CONTRACT_SHA256:
        fail("frozen contract SHA-256 drift")
    require_exact(ledger.get("schema"), LEDGER_SCHEMA, "ledger schema")
    require_exact(ledger.get("ledger_id"), LEDGER_ID, "ledger id")
    require_exact(ledger.get("baseline_commit"), "f19ec1a813ceb2d29be0a74a430293d8b998a574", "ledger baseline")
    require_exact(
        ledger.get("classification_catalog_sha256"),
        LEDGER_CLASSIFICATION_CATALOG_SHA256,
        "ledger classification catalog",
    )
    rows = ledger.get("bindings")
    if not isinstance(rows, list):
        fail("ledger bindings must be a list")
    by_path: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("binding_path"), str):
            fail("invalid ledger binding row")
        path = row["binding_path"]
        if path in by_path:
            fail("duplicate ledger binding path")
        by_path[path] = row
    exact = {
        path
        for path, row in by_path.items()
        if row.get("local_fill_rule") == "EXACT_COMMITTED_ARTIFACT_ONLY"
    }
    upstream = {
        path
        for path, row in by_path.items()
        if row.get("local_fill_rule") == "BLOCKED_UNTIL_UPSTREAM_BINDING"
    }
    if len(exact) != 23 or upstream != EXPECTED_UPSTREAM_PATHS:
        fail("ledger exact-artifact or upstream-blocked set drift")
    for path in exact:
        row = by_path[path]
        require_exact(row.get("owner_class"), "local_deterministic", f"{path} owner")
        require_exact(row.get("required_stage"), "PRE_OUTPUT_ADMISSION", f"{path} stage")
        require_exact(row.get("value_kind"), "sha256", f"{path} kind")
        require_false(row.get("binding_satisfied"), f"{path} satisfaction")
        if row.get("binding_evidence") is not None:
            fail(f"{path} has binding evidence")
        require_false(row.get("unlocks_side_effect"), f"{path} unlock")
    return by_path, exact, upstream


def dependency_catalog_bytes(nodes: list[dict[str, Any]]) -> bytes:
    return canonical_compact_bytes(nodes)


def derive_primary_class(
    classes: set[str], *, has_blocked_upstream: bool, has_unrepresented_upstream: bool
) -> str:
    if has_blocked_upstream or has_unrepresented_upstream:
        return "UPSTREAM_RUNTIME_DEPENDENT"
    if "custodian_private" in classes:
        return "CUSTODIAN_PRIVATE_DEPENDENT"
    if "owner_policy" in classes:
        return "OWNER_POLICY_DEPENDENT"
    if "runtime_capture" in classes:
        return "UPSTREAM_RUNTIME_DEPENDENT"
    return "INDEPENDENT_PUBLIC"


def validate_graph(
    graph: dict[str, Any],
    graph_raw: bytes,
    ledger: dict[str, Any],
    ledger_raw: bytes,
    contract_raw: bytes,
    root: Path | None,
) -> dict[str, Any]:
    require_exact_keys(graph, EXPECTED_TOP_LEVEL_KEYS, "graph")
    if graph_raw != canonical_pretty_bytes(graph):
        fail("graph is not canonical pretty JSON")
    require_exact(graph.get("schema"), GRAPH_SCHEMA, "graph schema")
    require_exact(graph.get("graph_id"), GRAPH_ID, "graph id")
    require_exact(graph.get("date"), "2026-07-14", "graph date")
    require_exact(graph.get("baseline_commit"), BASELINE_COMMIT, "graph baseline")
    by_binding, exact_paths, upstream_paths = validate_source_inputs(
        ledger, ledger_raw, contract_raw
    )

    require_exact(
        graph.get("scope"),
        {
            "graph_coverage": "EXACT_23_EXACT_COMMITTED_ARTIFACT_ONLY_LEDGER_PATHS",
            "old_successor_data_reuse": "PROHIBITED",
            "old_successor_mechanism_reuse": "ALLOWED_WITH_NEW_SOURCE_ARTIFACTS_AND_TESTS",
            "prerequisite_scope": "SOURCE_ARTIFACT_IMPLEMENTATION_FREEZE_NOT_FULL_REAL_RUN_INPUT_CLOSURE",
            "real_run_input_closure_source": "LIVE_BINDING_LEDGER_91_SCALARS_PLUS_4_STAGE_OBLIGATIONS",
        },
        "scope",
    )
    require_exact(
        graph.get("readiness_policy"),
        {
            "controlling_dependency_precedence": CONTROLLING_DEPENDENCY_PRECEDENCE,
            "external_dependencies_definition": "DIRECT_SOURCE_FREEZE_SEMANTIC_BLOCKERS_ONLY_NOT_EXECUTION_INSTANCE_CLOSURE",
            "implementation_ready_definition": "EXACT_ARTIFACT_BYTES_COMMITTED_AND_SOURCE_BOUND_WITH_ALL_LOCAL_DEPENDENCIES_IMPLEMENTED",
            "initial_public_authoring_frontier_definition": "INDEPENDENT_PUBLIC_NODES_WITH_ZERO_LOCAL_DEPENDENCIES",
            "live_binding_ready_definition": "IMPLEMENTATION_READY_AND_ALL_LEDGER_BINDINGS_AND_STAGE_OBLIGATIONS_SATISFIED",
            "public_authoring_eligible_definition": "PRIMARY_CLASS_INDEPENDENT_PUBLIC_AND_ALL_LOCAL_DEPENDENCIES_PUBLIC_AUTHORING_ELIGIBLE",
        },
        "readiness policy",
    )

    evidence = graph.get("evidence_catalog")
    if not isinstance(evidence, list) or len(evidence) != 9:
        fail("evidence catalog must contain exactly nine rows")
    evidence_paths: list[str] = []
    for index, row in enumerate(evidence):
        require_exact_keys(row, EXPECTED_EVIDENCE_KEYS, f"evidence[{index}]")
        path = require_safe_relative_path(row.get("path"), f"evidence[{index}].path")
        evidence_paths.append(path)
        if not isinstance(row.get("role"), str) or not LABEL_RE.fullmatch(row["role"]):
            fail(f"evidence[{index}] role invalid")
        if row.get("status") not in {"FROZEN_SOURCE_INPUT", "MECHANISM_ONLY"}:
            fail(f"evidence[{index}] status invalid")
        if row.get("reuse_scope") not in {
            "DEPENDENCY_ANALYSIS_SOURCE_ONLY",
            "MECHANISM_ONLY_NOT_BINDING_OR_CONFIRMATORY_DATA",
            "PUBLIC_CONTRACT_AND_SYNTHETIC_ARITHMETIC_ONLY",
        }:
            fail(f"evidence[{index}] reuse scope invalid")
        require_false(row.get("may_satisfy_live_binding"), f"evidence[{index}] binding")
        digest = row.get("sha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            fail(f"evidence[{index}] SHA-256 invalid")
        if root is not None:
            evidence_file = require_regular_unaliased(root, path, f"evidence[{index}]")
            try:
                observed = sha256_bytes(evidence_file.read_bytes())
            except OSError as exc:
                fail(f"cannot read evidence[{index}]: {exc}")
            if observed != digest:
                fail(f"evidence[{index}] byte hash drift")
    if evidence_paths != sorted(evidence_paths) or len(evidence_paths) != len(set(evidence_paths)):
        fail("evidence paths must be sorted and unique")
    observed_evidence_catalog = sha256_bytes(canonical_compact_bytes(evidence))
    require_exact(
        graph.get("evidence_catalog_sha256"),
        observed_evidence_catalog,
        "self-reported evidence catalog hash",
    )
    require_exact(observed_evidence_catalog, EVIDENCE_CATALOG_SHA256, "frozen evidence catalog hash")

    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != 23:
        fail("graph must contain exactly 23 nodes")
    paths = [node.get("artifact_binding_path") if isinstance(node, dict) else None for node in nodes]
    if any(not isinstance(path, str) for path in paths):
        fail("node artifact paths must be strings")
    if paths != sorted(paths) or len(paths) != len(set(paths)) or set(paths) != exact_paths:
        fail("node coverage, order, or uniqueness drift")
    node_by_path = {node["artifact_binding_path"]: node for node in nodes}
    evidence_path_set = set(evidence_paths)
    local_edge_count = 0
    external_edge_counts: Counter[str] = Counter()
    upstream_edge_count = 0
    unrepresented_upstream_edge_count = 0

    for index, node in enumerate(nodes):
        path = node["artifact_binding_path"]
        require_exact_keys(node, EXPECTED_NODE_KEYS, f"node[{index}]")
        if not isinstance(node.get("artifact_kind"), str) or not LABEL_RE.fullmatch(node["artifact_kind"]):
            fail(f"{path} artifact kind invalid")
        require_false(node.get("binding_satisfied"), f"{path} binding satisfaction")
        require_false(node.get("unlocks_side_effect"), f"{path} unlock")
        if node.get("binding_evidence") is not None:
            fail(f"{path} binding evidence must be null")
        for key in [
            "committed_artifact_blob_oid",
            "committed_artifact_repo_path",
            "committed_artifact_sha256",
        ]:
            if node.get(key) is not None:
                fail(f"{path} {key} must be null")
        require_exact(
            node.get("implementation_status"),
            "PLANNED_NOT_IMPLEMENTED_OR_BOUND",
            f"{path} implementation status",
        )
        require_exact(node.get("required_stage"), "PRE_OUTPUT_ADMISSION", f"{path} stage")
        refs = require_sorted_unique_strings(node.get("evidence_refs"), f"{path} evidence refs")
        if not refs or not set(refs) <= evidence_path_set:
            fail(f"{path} evidence refs escape frozen catalog")

        local = require_sorted_unique_strings(node.get("local_dependencies"), f"{path} local dependencies")
        if path in local or not set(local) <= exact_paths:
            fail(f"{path} has invalid local dependency")
        local_edge_count += len(local)

        external = node.get("external_dependencies")
        if not isinstance(external, list):
            fail(f"{path} external dependencies must be a list")
        external_names: list[str] = []
        for item_index, item in enumerate(external):
            require_exact_keys(
                item,
                {"binding_path", "owner_class", "reason_code"},
                f"{path}.external[{item_index}]",
            )
            dependency_path = item.get("binding_path")
            if not isinstance(dependency_path, str):
                fail(f"{path} external dependency path invalid")
            external_names.append(dependency_path)
            if dependency_path not in by_binding or dependency_path in exact_paths or dependency_path in upstream_paths:
                fail(f"{path} external dependency is outside allowed pool")
            ledger_row = by_binding[dependency_path]
            owner = item.get("owner_class")
            if owner not in {"owner_policy", "custodian_private", "runtime_capture"}:
                fail(f"{path} external owner class invalid")
            require_exact(ledger_row.get("owner_class"), owner, f"{path} external owner projection")
            require_exact(
                ledger_row.get("local_fill_rule"),
                "PROHIBITED_LOCAL_SYNTHESIS",
                f"{path} external fill rule",
            )
            require_false(ledger_row.get("binding_satisfied"), f"{path} external satisfaction")
            if ledger_row.get("binding_evidence") is not None:
                fail(f"{path} external evidence is not null")
            require_false(ledger_row.get("unlocks_side_effect"), f"{path} external unlock")
            if not isinstance(item.get("reason_code"), str) or not REASON_RE.fullmatch(item["reason_code"]):
                fail(f"{path} external reason code invalid")
            external_edge_counts[owner] += 1
        if external_names != sorted(external_names) or len(external_names) != len(set(external_names)):
            fail(f"{path} external dependencies must be sorted and unique")

        upstream = node.get("blocked_upstream_dependencies")
        if not isinstance(upstream, list):
            fail(f"{path} upstream dependencies must be a list")
        upstream_names: list[str] = []
        for item_index, item in enumerate(upstream):
            require_exact_keys(item, {"binding_path", "reason_code"}, f"{path}.upstream[{item_index}]")
            dependency_path = item.get("binding_path")
            if not isinstance(dependency_path, str) or dependency_path not in upstream_paths:
                fail(f"{path} upstream dependency is outside frozen set")
            upstream_names.append(dependency_path)
            ledger_row = by_binding[dependency_path]
            require_exact(ledger_row.get("owner_class"), "local_deterministic", f"{path} upstream owner")
            require_false(ledger_row.get("binding_satisfied"), f"{path} upstream satisfaction")
            if ledger_row.get("binding_evidence") is not None:
                fail(f"{path} upstream evidence is not null")
            require_false(ledger_row.get("unlocks_side_effect"), f"{path} upstream unlock")
            if not isinstance(item.get("reason_code"), str) or not REASON_RE.fullmatch(item["reason_code"]):
                fail(f"{path} upstream reason code invalid")
            upstream_edge_count += 1
        if upstream_names != sorted(upstream_names) or len(upstream_names) != len(set(upstream_names)):
            fail(f"{path} upstream dependencies must be sorted and unique")
        unrepresented = require_sorted_unique_strings(
            node.get("unrepresented_upstream_dependencies"),
            f"{path} unrepresented upstream dependencies",
        )
        if any(not REASON_RE.fullmatch(item) for item in unrepresented):
            fail(f"{path} unrepresented upstream dependency symbol invalid")
        unrepresented_upstream_edge_count += len(unrepresented)
        if set(local) & set(external_names) or set(local) & set(upstream_names) or set(external_names) & set(upstream_names):
            fail(f"{path} dependency classes overlap")

    observed_dependency_catalog = sha256_bytes(dependency_catalog_bytes(nodes))
    require_exact(
        graph.get("dependency_catalog_sha256"),
        observed_dependency_catalog,
        "self-reported dependency catalog hash",
    )
    require_exact(observed_dependency_catalog, DEPENDENCY_CATALOG_SHA256, "frozen dependency catalog hash")

    successors: dict[str, list[str]] = {path: [] for path in paths}
    indegree: dict[str, int] = {}
    for path, node in node_by_path.items():
        dependencies = node["local_dependencies"]
        indegree[path] = len(dependencies)
        for dependency in dependencies:
            successors[dependency].append(path)
    for value in successors.values():
        value.sort()
    heap = [path for path in paths if indegree[path] == 0]
    heapq.heapify(heap)
    topological: list[str] = []
    while heap:
        path = heapq.heappop(heap)
        topological.append(path)
        for successor in successors[path]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                heapq.heappush(heap, successor)
    if len(topological) != len(paths):
        fail("local dependency graph contains a cycle")

    def reaches(start: str, target: str) -> bool:
        pending = list(node_by_path[start]["local_dependencies"])
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current not in seen:
                seen.add(current)
                pending.extend(node_by_path[current]["local_dependencies"])
        return False

    for path, node in node_by_path.items():
        for dependency in node["local_dependencies"]:
            if any(
                reaches(other, dependency)
                for other in node["local_dependencies"]
                if other != dependency
            ):
                fail(f"{path} contains a redundant transitive dependency edge")

    waves: dict[str, int] = {}
    authoring_eligibility: dict[str, bool] = {}
    for path in topological:
        node = node_by_path[path]
        dependencies = node["local_dependencies"]
        waves[path] = 0 if not dependencies else 1 + max(waves[item] for item in dependencies)
        classes = {item["owner_class"] for item in node["external_dependencies"]}
        expected_class = derive_primary_class(
            classes,
            has_blocked_upstream=bool(node["blocked_upstream_dependencies"]),
            has_unrepresented_upstream=bool(node["unrepresented_upstream_dependencies"]),
        )
        require_exact(node.get("primary_readiness_class"), expected_class, f"{path} readiness class")
        expected_eligible = expected_class == "INDEPENDENT_PUBLIC" and all(
            authoring_eligibility[dependency] for dependency in dependencies
        )
        authoring_eligibility[path] = expected_eligible
        if node.get("public_authoring_eligible") is not expected_eligible:
            fail(f"{path} public authoring eligibility drift")

    class_counts = Counter(node["primary_readiness_class"] for node in nodes)
    independent = {
        path for path, node in node_by_path.items() if node["public_authoring_eligible"] is True
    }
    frontier = sorted(path for path in independent if not node_by_path[path]["local_dependencies"])
    independent_wave_map: dict[int, list[str]] = defaultdict(list)
    for path in sorted(independent):
        independent_wave_map[waves[path]].append(path)
    independent_waves = [
        {"artifact_paths": independent_wave_map[wave], "wave": wave}
        for wave in sorted(independent_wave_map)
    ]
    dependency_targets = {dependency for node in nodes for dependency in node["local_dependencies"]}
    sinks = [path for path in paths if path not in dependency_targets]
    expected_summary = {
        "artifact_commit_evidence_count": 0,
        "artifact_count": 23,
        "blocked_upstream_dependency_edge_count": upstream_edge_count,
        "custodian_private_dependency_edge_count": external_edge_counts["custodian_private"],
        "custodian_private_dependent_count": class_counts["CUSTODIAN_PRIVATE_DEPENDENT"],
        "dag_max_wave": max(waves.values()),
        "dag_root_count": sum(not node["local_dependencies"] for node in nodes),
        "dag_sink_count": len(sinks),
        "direct_external_dependency_edge_count": sum(external_edge_counts.values()),
        "direct_local_dependency_edge_count": local_edge_count,
        "implementation_ready_count": 0,
        "independent_authoring_wave_count": len(independent_waves),
        "independent_authoring_waves": independent_waves,
        "independent_public_count": class_counts["INDEPENDENT_PUBLIC"],
        "initial_public_authoring_frontier": frontier,
        "initial_public_authoring_frontier_count": len(frontier),
        "live_binding_ready_count": 0,
        "owner_policy_dependency_edge_count": external_edge_counts["owner_policy"],
        "owner_policy_dependent_count": class_counts["OWNER_POLICY_DEPENDENT"],
        "recommended_first_pack": EXPECTED_FIRST_PACK,
        "recommended_first_pack_count": len(EXPECTED_FIRST_PACK),
        "runtime_capture_dependency_edge_count": external_edge_counts["runtime_capture"],
        "topological_node_count": len(topological),
        "unrepresented_upstream_dependency_edge_count": unrepresented_upstream_edge_count,
        "upstream_runtime_dependent_count": class_counts["UPSTREAM_RUNTIME_DEPENDENT"],
    }
    require_exact(graph.get("summary"), expected_summary, "derived graph summary")
    if not set(EXPECTED_FIRST_PACK) <= set(frontier):
        fail("recommended first pack is outside the public authoring frontier")

    require_exact(
        graph.get("admission"),
        {
            "artifact_binding_complete": False,
            "committed_artifact_count": 0,
            "decision": "PLANNING_GRAPH_VALIDATED_FAIL_CLOSED",
            "implementation_ready_count": 0,
            "live_binding_ready_count": 0,
            "real_run_admitted": False,
            "side_effects_unlocked": "NONE",
        },
        "admission boundary",
    )
    authority = require_exact_keys(graph.get("authority"), EXPECTED_AUTHORITY_KEYS, "authority")
    for key, value in authority.items():
        require_false(value, f"authority.{key}")

    return {
        "artifact_count": len(nodes),
        "blocked_upstream_edges": upstream_edge_count,
        "custodian_edges": external_edge_counts["custodian_private"],
        "dependency_catalog_sha256": observed_dependency_catalog,
        "evidence_catalog_sha256": observed_evidence_catalog,
        "external_edges": sum(external_edge_counts.values()),
        "frontier_count": len(frontier),
        "graph_sha256": sha256_bytes(graph_raw),
        "independent_count": class_counts["INDEPENDENT_PUBLIC"],
        "local_edges": local_edge_count,
        "owner_edges": external_edge_counts["owner_policy"],
        "runtime_edges": external_edge_counts["runtime_capture"],
        "unrepresented_upstream_edges": unrepresented_upstream_edge_count,
    }


def set_path(value: dict[str, Any], path: tuple[Any, ...], replacement: Any) -> None:
    cursor: Any = value
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = replacement


def recompute_dependency_catalog(graph: dict[str, Any]) -> None:
    graph["dependency_catalog_sha256"] = sha256_bytes(dependency_catalog_bytes(graph["nodes"]))


def recompute_evidence_catalog(graph: dict[str, Any]) -> None:
    graph["evidence_catalog_sha256"] = sha256_bytes(canonical_compact_bytes(graph["evidence_catalog"]))


def remove_local_edge_and_recompute(graph: dict[str, Any]) -> None:
    graph["nodes"][0]["local_dependencies"].pop()
    recompute_dependency_catalog(graph)


def swap_external_edges_and_recompute(graph: dict[str, Any]) -> None:
    first = graph["nodes"][0]["external_dependencies"][0]
    second = graph["nodes"][1]["external_dependencies"][0]
    first["binding_path"], second["binding_path"] = second["binding_path"], first["binding_path"]
    graph["nodes"][0]["external_dependencies"].sort(key=lambda row: row["binding_path"])
    graph["nodes"][1]["external_dependencies"].sort(key=lambda row: row["binding_path"])
    recompute_dependency_catalog(graph)


def reclassify_external_and_recompute(graph: dict[str, Any]) -> None:
    graph["nodes"][0]["external_dependencies"][0]["owner_class"] = "runtime_capture"
    graph["nodes"][0]["primary_readiness_class"] = "UPSTREAM_RUNTIME_DEPENDENT"
    recompute_dependency_catalog(graph)


def substitute_evidence_and_recompute(graph: dict[str, Any]) -> None:
    graph["evidence_catalog"][0]["path"] = "Cargo.lock"
    graph["evidence_catalog"][0]["sha256"] = "5ebad772d0d0d48d1414bf02939feeb56ad0aa3e15aa7ee0db6fb4cb46e6c613"
    graph["evidence_catalog"].sort(key=lambda row: row["path"])
    recompute_evidence_catalog(graph)


def remove_external_and_recompute(graph: dict[str, Any]) -> None:
    graph["nodes"][0]["external_dependencies"].pop()
    recompute_dependency_catalog(graph)


def alter_external_reason_and_recompute(graph: dict[str, Any]) -> None:
    graph["nodes"][0]["external_dependencies"][0]["reason_code"] = "REBOUND_REASON"
    recompute_dependency_catalog(graph)


def remove_unrepresented_and_recompute(graph: dict[str, Any]) -> None:
    graph["nodes"][0]["unrepresented_upstream_dependencies"].pop()
    recompute_dependency_catalog(graph)


def add_unrepresented_and_recompute(graph: dict[str, Any]) -> None:
    graph["nodes"][0]["unrepresented_upstream_dependencies"].append(
        "FAKE_UPSTREAM_INTERFACE_UNREPRESENTED"
    )
    graph["nodes"][0]["unrepresented_upstream_dependencies"].sort()
    recompute_dependency_catalog(graph)


def run_graph_self_test(
    graph: dict[str, Any], ledger: dict[str, Any], ledger_raw: bytes, contract_raw: bytes
) -> int:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("schema", lambda x: set_path(x, ("schema",), "wrong")),
        ("graph-id", lambda x: set_path(x, ("graph_id",), "wrong")),
        ("date", lambda x: set_path(x, ("date",), "2026-07-15")),
        ("baseline", lambda x: set_path(x, ("baseline_commit",), "0" * 40)),
        ("remove-node", lambda x: x["nodes"].pop()),
        ("duplicate-node", lambda x: x["nodes"].append(copy.deepcopy(x["nodes"][0]))),
        ("reorder-node", lambda x: x["nodes"].reverse()),
        ("wrong-node-path", lambda x: set_path(x, ("nodes", 0, "artifact_binding_path"), "latency.total_expected_units")),
        ("binding-satisfied", lambda x: set_path(x, ("nodes", 0, "binding_satisfied"), True)),
        ("binding-false-int", lambda x: set_path(x, ("nodes", 0, "binding_satisfied"), 0)),
        ("binding-evidence", lambda x: set_path(x, ("nodes", 0, "binding_evidence"), {"sha256": "0" * 64})),
        ("artifact-path", lambda x: set_path(x, ("nodes", 0, "committed_artifact_repo_path"), "scripts/fake.py")),
        ("artifact-hash", lambda x: set_path(x, ("nodes", 0, "committed_artifact_sha256"), "0" * 64)),
        ("artifact-oid", lambda x: set_path(x, ("nodes", 0, "committed_artifact_blob_oid"), "0" * 40)),
        ("implementation", lambda x: set_path(x, ("nodes", 0, "implementation_status"), "IMPLEMENTED")),
        ("node-extra-key", lambda x: x["nodes"][0].__setitem__("ready", False)),
        ("false-authoring", lambda x: set_path(x, ("nodes", 0, "public_authoring_eligible"), True)),
        ("false-readiness", lambda x: set_path(x, ("nodes", 0, "primary_readiness_class"), "INDEPENDENT_PUBLIC")),
        ("unlock", lambda x: set_path(x, ("nodes", 0, "unlocks_side_effect"), True)),
        ("missing-local-edge", remove_local_edge_and_recompute),
        ("missing-local-target", lambda x: set_path(x, ("nodes", 0, "local_dependencies", 0), "missing.sha256")),
        ("self-cycle", lambda x: set_path(x, ("nodes", 0, "local_dependencies", 0), x["nodes"][0]["artifact_binding_path"])),
        ("two-cycle", lambda x: x["nodes"][1]["local_dependencies"].append(x["nodes"][0]["artifact_binding_path"])),
        ("external-swap", swap_external_edges_and_recompute),
        ("external-reclass", reclassify_external_and_recompute),
        ("external-remove", remove_external_and_recompute),
        ("external-reason", alter_external_reason_and_recompute),
        ("external-to-upstream", lambda x: set_path(x, ("nodes", 0, "external_dependencies", 0, "binding_path"), "latency.total_expected_units")),
        ("external-local-placeholder", lambda x: set_path(x, ("nodes", 0, "external_dependencies", 0, "binding_path"), "context_and_result.exact_tokenizer_code_sha256")),
        ("upstream-to-external", lambda x: set_path(x, ("nodes", 0, "blocked_upstream_dependencies", 0, "binding_path"), "generation.execution_profile_sha256")),
        ("unrepresented-remove", remove_unrepresented_and_recompute),
        ("unrepresented-add", add_unrepresented_and_recompute),
        ("frontier-add-blocked", lambda x: x["summary"]["initial_public_authoring_frontier"].append("generation.harness_sha256")),
        ("wave", lambda x: set_path(x, ("summary", "independent_authoring_waves", 0, "wave"), 1)),
        ("ready-count", lambda x: set_path(x, ("summary", "implementation_ready_count"), 1)),
        ("count-float", lambda x: set_path(x, ("summary", "artifact_count"), 23.0)),
        ("first-pack", lambda x: x["summary"]["recommended_first_pack"].pop()),
        ("admit", lambda x: set_path(x, ("admission", "real_run_admitted"), True)),
        ("authority", lambda x: set_path(x, ("authority", "scientific_claim"), True)),
        ("authority-false-int", lambda x: set_path(x, ("authority", "scientific_claim"), 0)),
        ("evidence-bind", lambda x: set_path(x, ("evidence_catalog", 0, "may_satisfy_live_binding"), True)),
        ("evidence-substitution", substitute_evidence_and_recompute),
        ("evidence-ref", lambda x: set_path(x, ("nodes", 0, "evidence_refs", 0), "Cargo.lock")),
        ("catalog", lambda x: set_path(x, ("dependency_catalog_sha256",), "f" * 64)),
    ]
    rejected = 0
    for label, mutate in mutations:
        trial = copy.deepcopy(graph)
        mutate(trial)
        raw = canonical_pretty_bytes(trial)
        try:
            validate_graph(trial, raw, ledger, ledger_raw, contract_raw, None)
        except GraphError:
            rejected += 1
        else:
            fail(f"graph self-test mutation accepted: {label}")
    return rejected


def run_source_self_test(
    graph: dict[str, Any], graph_raw: bytes, ledger: dict[str, Any], ledger_raw: bytes, contract_raw: bytes
) -> int:
    mutations: list[tuple[str, str]] = [
        ("ledger-byte", "ledger"),
        ("ledger-classification", "ledger-classification"),
        ("contract-byte", "contract"),
        ("graph-noncanonical", "graph"),
    ]
    rejected = 0
    for label, target in mutations:
        trial_ledger = copy.deepcopy(ledger)
        trial_ledger_raw = ledger_raw
        trial_contract_raw = contract_raw
        trial_graph_raw = graph_raw
        if target == "ledger":
            trial_ledger_raw = ledger_raw + b" "
        elif target == "ledger-classification":
            trial_ledger["bindings"][0]["owner_class"] = "owner_policy"
            trial_ledger_raw = canonical_pretty_bytes(trial_ledger)
        elif target == "contract":
            trial_contract_raw = contract_raw + b" "
        else:
            trial_graph_raw = graph_raw + b" "
        try:
            validate_graph(
                graph,
                trial_graph_raw,
                trial_ledger,
                trial_ledger_raw,
                trial_contract_raw,
                None,
            )
        except GraphError:
            rejected += 1
        else:
            fail(f"source self-test mutation accepted: {label}")
    return rejected


def render_receipt(graph: dict[str, Any], metrics: dict[str, Any]) -> str:
    summary = graph["summary"]
    rows = [
        ("schema", GRAPH_SCHEMA),
        ("graph_id", GRAPH_ID),
        ("graph_sha256", metrics["graph_sha256"]),
        ("baseline_commit", BASELINE_COMMIT),
        ("ledger_sha256", LEDGER_SHA256),
        ("contract_sha256", CONTRACT_SHA256),
        ("dependency_catalog_sha256", metrics["dependency_catalog_sha256"]),
        ("evidence_catalog_sha256", metrics["evidence_catalog_sha256"]),
        ("planning_graph_complete", "true"),
        ("artifact_count", metrics["artifact_count"]),
        ("direct_local_dependency_edge_count", metrics["local_edges"]),
        ("direct_external_dependency_edge_count", metrics["external_edges"]),
        ("owner_policy_dependency_edge_count", metrics["owner_edges"]),
        ("custodian_private_dependency_edge_count", metrics["custodian_edges"]),
        ("runtime_capture_dependency_edge_count", metrics["runtime_edges"]),
        ("blocked_upstream_dependency_edge_count", metrics["blocked_upstream_edges"]),
        ("unrepresented_upstream_dependency_edge_count", metrics["unrepresented_upstream_edges"]),
        ("independent_public_count", metrics["independent_count"]),
        ("owner_policy_dependent_count", summary["owner_policy_dependent_count"]),
        ("custodian_private_dependent_count", summary["custodian_private_dependent_count"]),
        ("upstream_runtime_dependent_count", summary["upstream_runtime_dependent_count"]),
        ("initial_public_authoring_frontier_count", metrics["frontier_count"]),
        ("recommended_first_pack_count", summary["recommended_first_pack_count"]),
        ("independent_authoring_wave_count", summary["independent_authoring_wave_count"]),
        ("artifact_commit_evidence_count", 0),
        ("committed_artifact_count", 0),
        ("implementation_ready_count", 0),
        ("live_binding_ready_count", 0),
        ("artifact_binding_complete", "false"),
        ("decision", "PLANNING_GRAPH_VALIDATED_FAIL_CLOSED"),
        ("real_run_admitted", "false"),
        ("side_effects_unlocked", "NONE"),
        ("authority_true_count", 0),
        ("old_successor_data_reuse", "PROHIBITED"),
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
        graph, graph_raw = read_strict_json(root / GRAPH_PATH, "graph")
        ledger, ledger_raw = read_strict_json(root / LEDGER_PATH, "ledger")
        _, contract_raw = read_strict_json(root / CONTRACT_PATH, "contract")
        metrics = validate_graph(graph, graph_raw, ledger, ledger_raw, contract_raw, root)
        if args.self_test:
            graph_rejected = run_graph_self_test(
                graph, ledger, ledger_raw, contract_raw
            )
            source_rejected = run_source_self_test(
                graph, graph_raw, ledger, ledger_raw, contract_raw
            )
            print(
                "SELF_TEST_OK"
                f"\tgraph_mutations_rejected={graph_rejected}"
                f"\tsource_mutations_rejected={source_rejected}"
                f"\ttotal_mutations_rejected={graph_rejected + source_rejected}"
            )
        else:
            sys.stdout.write(render_receipt(graph, metrics))
    except GraphError as exc:
        print(f"Track B artifact dependency graph check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
