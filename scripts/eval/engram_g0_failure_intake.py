#!/usr/bin/env python3
"""Capture and classify G0 precision/generalization failures without live writes.

Real intake specs contain private queries and therefore belong only under the
repository's ignored ``data/`` tree. ``capture`` makes an online SQLite backup,
runs each current-baseline observation against a fresh disposable clone, and
emits only hashes and ranks. ``evaluate`` never opens a database or calls
Agent-Bridge.

No verdict from this tool grants candidate implementation, corpus-freeze,
ranking, memory-write, or runtime authority. A positive G0 receipt only permits
the next design step: independently freeze a G1 grouped corpus contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

from portfolio_continuity_ab_trial import (
    McpClient,
    TrialError,
    mcp_text,
    observe_binary_identity,
    sha256_file,
)


CONTRACT_SCHEMA = "agent_bridge.engram_g0_failure_intake_contract.v0"
PRIVATE_SPEC_SCHEMA = "agent_bridge.engram_g0_private_intake_spec.v0"
PACKET_SCHEMA = "agent_bridge.engram_g0_failure_replay_packet.v0"
RECEIPT_SCHEMA = "agent_bridge.engram_g0_failure_receipt.v0"
CONTRACT_RECEIPT_SCHEMA = "agent_bridge.engram_g0_contract_receipt.v0"
BASELINE_ENV_RECEIPT_SCHEMA = "agent_bridge.engram_g0_baseline_environment_receipt.v0"

EVIDENCE_CLASSES = {"synthetic_contract_test", "consumer_owned_real"}
PROBE_CLASSES = ("exact", "related", "unrelated")
RELEVANT_SIGNATURES = {"generalization_gap", "overgeneralization_gap"}
MAX_G0_EPISODE_GROUPS = 3
MAX_SYNTHETIC_EPISODE_GROUPS = 4
MAX_EXPECTED_TARGET_KEYS = 32
MAX_JSON_INPUT_BYTES = 8 * 1024 * 1024
MAX_PERCEPTION_FILTER_STATE_BYTES = 16 * 1024 * 1024
BASELINE_ENVIRONMENT_KEYS = (
    "AB_BIOCORTEX_RETRIEVAL_DISABLE",
    "AB_BIOCORTEX_RETRIEVAL_OPT_IN",
    "AGENT_BRIDGE_COACTIVATION_RERANK_DISABLE",
    "AGENT_BRIDGE_CORRECTION_COSURFACE",
    "AGENT_BRIDGE_EMBED_BACKEND",
    "AGENT_BRIDGE_EMBED_REMOTE_URL",
    "AGENT_BRIDGE_FTS_OR_PRIMARY",
    "AGENT_BRIDGE_FUSION_SHADOW",
    "AGENT_BRIDGE_MEMORY_CLASS_QUOTA",
    "AGENT_BRIDGE_MEMORY_SEARCH_EXCLUDE_KINDS",
    "AGENT_BRIDGE_ONNX_MODEL",
    "AGENT_BRIDGE_ONNX_MODEL_DIR",
    "AGENT_BRIDGE_OUTCOME_COLLECTOR",
    "AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH",
    "AGENT_BRIDGE_PROJECT_SCOPE_ALIASES",
    "AGENT_BRIDGE_RECALL_SEMANTIC_FALLBACK",
    "AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS",
    "AGENT_BRIDGE_SEED_BOOST_DISABLE",
    "AGENT_BRIDGE_SEED_STATE_PATH",
    "AGENT_BRIDGE_SEMANTIC_RANK_LEGACY",
    "AGENT_BRIDGE_SEMANTIC_W_COS",
    "AGENT_BRIDGE_SEMANTIC_W_FB",
    "AGENT_BRIDGE_SEMANTIC_W_IMP",
    "AGENT_BRIDGE_SEMANTIC_W_MEM",
    "HOME",
)
DURABLE_CONTENT_INDEX_TABLES = (
    "schema_meta",
    "memories",
    "memory_edges",
    "memories_fts",
    "memories_fts_config",
)
DURABLE_STATE_EXCLUDED_COLUMNS = {
    # Hybrid retrieval intentionally bumps these through memory_get. Because
    # they can influence later rankings, no observation may reuse its clone.
    "memories": {"last_accessed_at", "access_count"},
}
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
RAW_CONTENT_FIELDS = {
    "content",
    "expected_key",
    "expected_keys",
    "expected_target_keys",
    "memory_key",
    "prompt",
    "query",
    "raw_content",
    "raw_query",
    "text",
}


class InputError(ValueError):
    """Raised when a contract or packet violates the G0 boundary."""


def reject_json_constant(value: str) -> None:
    raise InputError(f"non-standard JSON constant is forbidden: {value}")


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise InputError("JSON object contains a duplicate field")
        out[key] = value
    return out


def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = read_stable_bounded_file(path, MAX_JSON_INPUT_BYTES, "JSON input")
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            parse_constant=reject_json_constant,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(f"failed to read {path}: {exc}") from exc
    return require_object(value, str(path)), raw


def render_json(value: Any, *, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        )
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_canonical(value: Any) -> str:
    return sha256_text(render_json(value))


def env_truthy(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip()
    return normalized == "1" or normalized.lower() == "true"


def resolve_perception_filter_state_path() -> Path | None:
    configured = os.environ.get("AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH")
    if configured:
        candidate = Path(configured)
        if candidate.exists():
            return candidate
    bases: list[Path] = []
    home = os.environ.get("HOME")
    if home:
        bases.extend(
            [
                Path(home) / "Projects/agent-bridge-seed/state_pf",
                Path(home) / "agent-bridge-seed/state_pf",
            ]
        )
    bases.append(Path("/Data/CascadeProjects/agent-bridge-seed/state_pf"))
    for base in bases:
        for name in ["perception_filter_state.json", "perception_filter_state_low.json"]:
            candidate = base / name
            if candidate.exists():
                return candidate
    return None


def read_stable_bounded_file(path: Path, max_bytes: int, label: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise InputError(f"failed to open {label}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise InputError(f"{label} must be a regular file")
        if before.st_size < 0 or before.st_size > max_bytes:
            raise InputError(f"{label} exceeds the bounded size")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise InputError(f"{label} ended during capture")
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after or len(data) != before.st_size:
        raise InputError(f"{label} changed during capture")
    return data


def observe_perception_filter_state() -> dict[str, Any]:
    if env_truthy(os.environ.get("AGENT_BRIDGE_SEED_BOOST_DISABLE")):
        return {
            "status": "disabled",
            "path": None,
            "data": None,
            "sha256": sha256_text("seed-boost-disabled"),
        }
    path = resolve_perception_filter_state_path()
    if path is None:
        return {
            "status": "absent",
            "path": None,
            "data": None,
            "sha256": sha256_text("perception-filter-state-absent"),
        }
    data = read_stable_bounded_file(
        path, MAX_PERCEPTION_FILTER_STATE_BYTES, "baseline sidecar state"
    )
    return {
        "status": "frozen",
        "path": path,
        "data": data,
        "sha256": sha256_bytes(data),
    }


def baseline_environment_observation(
    contract: dict[str, Any], perception_state: dict[str, Any]
) -> dict[str, Any]:
    values = {key: os.environ.get(key) for key in contract["environment_keys"]}
    values.update(
        {
            "AB_BIOCORTEX_RETRIEVAL_DISABLE": "1",
            "AGENT_BRIDGE_OUTCOME_COLLECTOR": "0",
            "AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS": "eval",
            "AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH": (
                f"{perception_state['status']}:{perception_state['sha256']}"
            ),
        }
    )
    if perception_state["status"] != "frozen":
        values["AGENT_BRIDGE_SEED_BOOST_DISABLE"] = "1"
    remote_url = os.environ.get("AGENT_BRIDGE_EMBED_REMOTE_URL", "").strip()
    embedding_transport = "local"
    if remote_url:
        try:
            parsed = urllib.parse.urlsplit(remote_url)
            _ = parsed.port
        except ValueError as exc:
            raise InputError("embedding delegation URL is malformed") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise InputError("private G0 replay permits only credential-free loopback embedding")
        embedding_transport = "loopback_delegated"
    return {
        "environment_sha256": sha256_canonical(values),
        "embedding_transport": embedding_transport,
        "perception_filter_state_status": perception_state["status"],
        "perception_filter_state_sha256": perception_state["sha256"],
    }


def freeze_perception_filter_state(
    perception_state: dict[str, Any], temp_dir: Path
) -> Path | None:
    if perception_state["status"] != "frozen":
        return None
    data = perception_state["data"]
    if not isinstance(data, bytes):
        raise InputError("frozen sidecar observation lost its bytes")
    destination = temp_dir / "perception_filter_state.frozen.json"
    descriptor = -1
    try:
        descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
            0o600,
        )
        handle = os.fdopen(descriptor, "wb")
        descriptor = -1
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except (OSError, ValueError) as exc:
        raise InputError("failed to freeze the baseline sidecar state") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if sha256_file(destination) != perception_state["sha256"]:
        raise InputError("frozen baseline sidecar state hash drifted")
    return destination


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{path} must be an object")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise InputError(f"{path} must be an array")
    return value


def require_string(value: Any, path: str, *, max_bytes: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{path} must be a non-empty string")
    if len(value.encode("utf-8")) > max_bytes:
        raise InputError(f"{path} exceeds the {max_bytes}-byte limit")
    return value


def require_label(value: Any, path: str) -> str:
    label = require_string(value, path, max_bytes=128)
    if not LABEL_RE.fullmatch(label):
        raise InputError(f"{path} must be a bounded machine label")
    return label


def require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise InputError(f"{path} must be boolean")
    return value


def require_nonnegative_int(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise InputError(f"{path} must be a non-negative integer")
    return value


def require_sha256(value: Any, path: str, *, nonzero: bool = False) -> str:
    digest = require_string(value, path, max_bytes=64)
    if not SHA256_RE.fullmatch(digest):
        raise InputError(f"{path} must be a lowercase SHA-256 digest")
    if nonzero and digest == "0" * 64:
        raise InputError(f"{path} must not be the all-zero placeholder")
    return digest


def require_commit(value: Any, path: str) -> str:
    commit = require_string(value, path, max_bytes=40)
    if not COMMIT_RE.fullmatch(commit):
        raise InputError(f"{path} must be a full lowercase Git commit")
    return commit


def reject_unknown_fields(value: dict[str, Any], allowed: set[str], path: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise InputError(f"{path} contains {len(unknown)} unsupported field(s)")


def reject_raw_content_fields(value: Any, path: str = "packet") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in RAW_CONTENT_FIELDS:
                raise InputError(f"{path} contains forbidden raw-content field {key!r}")
            reject_raw_content_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_raw_content_fields(child, f"{path}[{index}]")


def unique_strings(value: Any, path: str, *, labels: bool = False) -> list[str]:
    items = require_list(value, path)
    if not items:
        raise InputError(f"{path} must not be empty")
    out = [
        require_label(item, f"{path}[{index}]")
        if labels
        else require_string(item, f"{path}[{index}]", max_bytes=512)
        for index, item in enumerate(items)
    ]
    if len(out) != len(set(out)):
        raise InputError(f"{path} must not contain duplicates")
    return out


def validate_contract(value: dict[str, Any]) -> dict[str, Any]:
    reject_unknown_fields(
        value,
        {
            "schema",
            "contract_id",
            "stage",
            "baseline",
            "admission",
            "boundaries",
        },
        "contract",
    )
    if value.get("schema") != CONTRACT_SCHEMA:
        raise InputError(f"contract.schema must be {CONTRACT_SCHEMA}")
    contract_id = require_label(value.get("contract_id"), "contract.contract_id")
    if value.get("stage") != "g0_observed_failure_only":
        raise InputError("contract.stage must be g0_observed_failure_only")

    baseline = require_object(value.get("baseline"), "contract.baseline")
    reject_unknown_fields(
        baseline,
        {
            "retrieval_modes",
            "top_k",
            "exclude_kinds",
            "traffic_class",
            "environment_keys",
        },
        "contract.baseline",
    )
    modes = unique_strings(
        baseline.get("retrieval_modes"),
        "contract.baseline.retrieval_modes",
        labels=True,
    )
    if modes != ["fts", "hybrid", "semantic"]:
        raise InputError("contract baseline must freeze fts, hybrid, semantic in order")
    top_k = require_nonnegative_int(baseline.get("top_k"), "contract.baseline.top_k")
    if not 1 <= top_k <= 100:
        raise InputError("contract.baseline.top_k must be in [1, 100]")
    exclude_kinds = unique_strings(
        baseline.get("exclude_kinds"),
        "contract.baseline.exclude_kinds",
        labels=True,
    )
    environment_keys = unique_strings(
        baseline.get("environment_keys"),
        "contract.baseline.environment_keys",
    )
    if environment_keys != list(BASELINE_ENVIRONMENT_KEYS):
        raise InputError("contract baseline environment keys drifted")
    if baseline.get("traffic_class") != "eval":
        raise InputError("contract baseline traffic_class must be eval")

    admission = require_object(value.get("admission"), "contract.admission")
    reject_unknown_fields(
        admission,
        {
            "minimum_real_relevant_groups",
            "require_consumer_owned",
            "require_observed_before_candidate_selection",
            "forbid_candidate_authored_probes",
            "require_rights_cleared",
            "accepted_relevant_signatures",
        },
        "contract.admission",
    )
    minimum = require_nonnegative_int(
        admission.get("minimum_real_relevant_groups"),
        "contract.admission.minimum_real_relevant_groups",
    )
    if minimum != 1:
        raise InputError("G0 minimum must remain one observed group; G1 sets corpus size")
    for key in [
        "require_consumer_owned",
        "require_observed_before_candidate_selection",
        "forbid_candidate_authored_probes",
        "require_rights_cleared",
    ]:
        if require_bool(admission.get(key), f"contract.admission.{key}") is not True:
            raise InputError(f"contract.admission.{key} must remain true")
    signatures = unique_strings(
        admission.get("accepted_relevant_signatures"),
        "contract.admission.accepted_relevant_signatures",
        labels=True,
    )
    if set(signatures) != RELEVANT_SIGNATURES:
        raise InputError("contract relevant signatures must remain exactly the G0 pair")

    boundaries = require_object(value.get("boundaries"), "contract.boundaries")
    expected_boundaries = {
        "writes_live_store": False,
        "mutates_retrieval_order": False,
        "enables_candidate_mechanism": False,
        "contains_raw_content_in_receipt": False,
        "candidate_implementation_authority": False,
        "g1_corpus_freeze_authority": False,
        "runtime_promotion_authority": False,
    }
    reject_unknown_fields(boundaries, set(expected_boundaries), "contract.boundaries")
    for key, expected in expected_boundaries.items():
        if require_bool(boundaries.get(key), f"contract.boundaries.{key}") is not expected:
            raise InputError(f"contract.boundaries.{key} must remain {expected}")

    return {
        "contract_id": contract_id,
        "modes": modes,
        "top_k": top_k,
        "exclude_kinds": exclude_kinds,
        "environment_keys": environment_keys,
        "minimum_real_relevant_groups": minimum,
        "boundaries": expected_boundaries,
    }


def validate_application(value: Any, path: str) -> dict[str, str]:
    application = require_object(value, path)
    reject_unknown_fields(
        application,
        {
            "application_owner_id",
            "affected_workflow_id",
            "failure_id",
            "current_baseline_version",
        },
        path,
    )
    return {
        key: require_label(application.get(key), f"{path}.{key}")
        for key in [
            "application_owner_id",
            "affected_workflow_id",
            "failure_id",
            "current_baseline_version",
        ]
    }


def validate_provenance(value: Any, path: str) -> dict[str, Any]:
    provenance = require_object(value, path)
    reject_unknown_fields(
        provenance,
        {
            "consumer_owned",
            "observed_before_candidate_selection",
            "candidate_authored_probes",
            "rights_cleared",
            "source_identity_sha256",
            "consumer_review_receipt_sha256",
        },
        path,
    )
    return {
        "consumer_owned": require_bool(
            provenance.get("consumer_owned"), f"{path}.consumer_owned"
        ),
        "observed_before_candidate_selection": require_bool(
            provenance.get("observed_before_candidate_selection"),
            f"{path}.observed_before_candidate_selection",
        ),
        "candidate_authored_probes": require_bool(
            provenance.get("candidate_authored_probes"),
            f"{path}.candidate_authored_probes",
        ),
        "rights_cleared": require_bool(
            provenance.get("rights_cleared"), f"{path}.rights_cleared"
        ),
        "source_identity_sha256": require_sha256(
            provenance.get("source_identity_sha256"),
            f"{path}.source_identity_sha256",
        ),
        "consumer_review_receipt_sha256": require_sha256(
            provenance.get("consumer_review_receipt_sha256"),
            f"{path}.consumer_review_receipt_sha256",
        ),
    }


def validate_ranks(value: Any, contract: dict[str, Any], path: str) -> dict[str, int]:
    ranks = require_object(value, path)
    if set(ranks) != set(contract["modes"]):
        raise InputError(f"{path} must contain exactly the frozen baseline modes")
    out: dict[str, int] = {}
    for mode in contract["modes"]:
        rank = require_nonnegative_int(ranks.get(mode), f"{path}.{mode}")
        if rank > contract["top_k"]:
            raise InputError(f"{path}.{mode} exceeds the frozen top_k")
        out[mode] = rank
    return out


def validate_packet(value: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    reject_raw_content_fields(value)
    reject_unknown_fields(
        value,
        {
            "schema",
            "contract_id",
            "packet_id",
            "evidence_class",
            "application",
            "provenance",
            "replay",
            "episode_groups",
        },
        "packet",
    )
    if value.get("schema") != PACKET_SCHEMA:
        raise InputError(f"packet.schema must be {PACKET_SCHEMA}")
    if value.get("contract_id") != contract["contract_id"]:
        raise InputError("packet.contract_id does not match the contract")
    packet_id = require_label(value.get("packet_id"), "packet.packet_id")
    evidence_class = value.get("evidence_class")
    if evidence_class not in EVIDENCE_CLASSES:
        raise InputError("packet.evidence_class is unsupported")
    application = validate_application(value.get("application"), "packet.application")
    provenance = validate_provenance(value.get("provenance"), "packet.provenance")

    replay = require_object(value.get("replay"), "packet.replay")
    replay_fields = {
        "baseline_source_commit",
        "baseline_binary_sha256",
        "baseline_environment_sha256",
        "embedding_transport",
        "perception_filter_state_status",
        "perception_filter_state_sha256",
        "baseline_modes",
        "top_k",
        "traffic_class",
        "source_db_access_mode",
        "source_db_query_only",
        "source_db_total_changes_before",
        "source_db_total_changes_after",
        "base_snapshot_sha256_before",
        "base_snapshot_sha256_after",
        "base_snapshot_unchanged",
        "fresh_snapshot_per_probe_mode",
        "all_observation_snapshots_started_from_base",
        "durable_content_index_state_sha256_before",
        "durable_content_index_state_sha256_after",
        "durable_content_index_state_unchanged",
        "disposable_baseline_side_effects_confined",
        "baseline_observation_count",
        "live_memory_writes",
        "candidate_retrieval_order_mutations",
        "outcome_collector_enabled",
        "candidate_mechanism_enabled",
    }
    reject_unknown_fields(replay, replay_fields, "packet.replay")
    normalized_replay = {
        "baseline_source_commit": require_commit(
            replay.get("baseline_source_commit"), "packet.replay.baseline_source_commit"
        ),
        "baseline_binary_sha256": require_sha256(
            replay.get("baseline_binary_sha256"),
            "packet.replay.baseline_binary_sha256",
            nonzero=True,
        ),
        "baseline_environment_sha256": require_sha256(
            replay.get("baseline_environment_sha256"),
            "packet.replay.baseline_environment_sha256",
            nonzero=True,
        ),
        "embedding_transport": replay.get("embedding_transport"),
        "perception_filter_state_status": replay.get(
            "perception_filter_state_status"
        ),
        "perception_filter_state_sha256": require_sha256(
            replay.get("perception_filter_state_sha256"),
            "packet.replay.perception_filter_state_sha256",
            nonzero=True,
        ),
        "baseline_modes": unique_strings(
            replay.get("baseline_modes"), "packet.replay.baseline_modes", labels=True
        ),
        "top_k": require_nonnegative_int(replay.get("top_k"), "packet.replay.top_k"),
        "traffic_class": replay.get("traffic_class"),
        "source_db_access_mode": replay.get("source_db_access_mode"),
        "source_db_query_only": require_bool(
            replay.get("source_db_query_only"), "packet.replay.source_db_query_only"
        ),
        "source_db_total_changes_before": require_nonnegative_int(
            replay.get("source_db_total_changes_before"),
            "packet.replay.source_db_total_changes_before",
        ),
        "source_db_total_changes_after": require_nonnegative_int(
            replay.get("source_db_total_changes_after"),
            "packet.replay.source_db_total_changes_after",
        ),
        "base_snapshot_sha256_before": require_sha256(
            replay.get("base_snapshot_sha256_before"),
            "packet.replay.base_snapshot_sha256_before",
            nonzero=True,
        ),
        "base_snapshot_sha256_after": require_sha256(
            replay.get("base_snapshot_sha256_after"),
            "packet.replay.base_snapshot_sha256_after",
            nonzero=True,
        ),
        "base_snapshot_unchanged": require_bool(
            replay.get("base_snapshot_unchanged"),
            "packet.replay.base_snapshot_unchanged",
        ),
        "fresh_snapshot_per_probe_mode": require_bool(
            replay.get("fresh_snapshot_per_probe_mode"),
            "packet.replay.fresh_snapshot_per_probe_mode",
        ),
        "all_observation_snapshots_started_from_base": require_bool(
            replay.get("all_observation_snapshots_started_from_base"),
            "packet.replay.all_observation_snapshots_started_from_base",
        ),
        "durable_content_index_state_sha256_before": require_sha256(
            replay.get("durable_content_index_state_sha256_before"),
            "packet.replay.durable_content_index_state_sha256_before",
            nonzero=True,
        ),
        "durable_content_index_state_sha256_after": require_sha256(
            replay.get("durable_content_index_state_sha256_after"),
            "packet.replay.durable_content_index_state_sha256_after",
            nonzero=True,
        ),
        "durable_content_index_state_unchanged": require_bool(
            replay.get("durable_content_index_state_unchanged"),
            "packet.replay.durable_content_index_state_unchanged",
        ),
        "disposable_baseline_side_effects_confined": require_bool(
            replay.get("disposable_baseline_side_effects_confined"),
            "packet.replay.disposable_baseline_side_effects_confined",
        ),
        "baseline_observation_count": require_nonnegative_int(
            replay.get("baseline_observation_count"),
            "packet.replay.baseline_observation_count",
        ),
        "live_memory_writes": require_nonnegative_int(
            replay.get("live_memory_writes"), "packet.replay.live_memory_writes"
        ),
        "candidate_retrieval_order_mutations": require_nonnegative_int(
            replay.get("candidate_retrieval_order_mutations"),
            "packet.replay.candidate_retrieval_order_mutations",
        ),
        "outcome_collector_enabled": require_bool(
            replay.get("outcome_collector_enabled"),
            "packet.replay.outcome_collector_enabled",
        ),
        "candidate_mechanism_enabled": require_bool(
            replay.get("candidate_mechanism_enabled"),
            "packet.replay.candidate_mechanism_enabled",
        ),
    }
    replay_invariants = {
        "baseline_modes": contract["modes"],
        "top_k": contract["top_k"],
        "traffic_class": "eval",
        "source_db_access_mode": "ro",
        "source_db_query_only": True,
        "source_db_total_changes_before": 0,
        "source_db_total_changes_after": 0,
        "base_snapshot_unchanged": True,
        "fresh_snapshot_per_probe_mode": True,
        "all_observation_snapshots_started_from_base": True,
        "durable_content_index_state_unchanged": True,
        "disposable_baseline_side_effects_confined": True,
        "live_memory_writes": 0,
        "candidate_retrieval_order_mutations": 0,
        "outcome_collector_enabled": False,
        "candidate_mechanism_enabled": False,
    }
    if normalized_replay["embedding_transport"] not in {"local", "loopback_delegated"}:
        raise InputError("packet replay embedding_transport is unsupported")
    if normalized_replay["perception_filter_state_status"] not in {
        "frozen",
        "absent",
        "disabled",
    }:
        raise InputError("packet replay perception-filter status is unsupported")
    for key, expected in replay_invariants.items():
        if normalized_replay[key] != expected:
            raise InputError(f"packet.replay.{key} violates the read-only baseline boundary")
    if (
        normalized_replay["base_snapshot_sha256_before"]
        != normalized_replay["base_snapshot_sha256_after"]
    ):
        raise InputError("packet replay base snapshot changed")
    if (
        normalized_replay["durable_content_index_state_sha256_before"]
        != normalized_replay["durable_content_index_state_sha256_after"]
    ):
        raise InputError("packet durable content/index state changed during replay")

    groups = require_list(value.get("episode_groups"), "packet.episode_groups")
    if not groups:
        raise InputError("packet.episode_groups must not be empty")
    group_limit = (
        MAX_G0_EPISODE_GROUPS
        if evidence_class == "consumer_owned_real"
        else MAX_SYNTHETIC_EPISODE_GROUPS
    )
    if len(groups) > group_limit:
        raise InputError("packet exceeds the bounded G0 episode-group limit")
    expected_observations = len(groups) * len(PROBE_CLASSES) * len(contract["modes"])
    if normalized_replay["baseline_observation_count"] != expected_observations:
        raise InputError("packet baseline_observation_count does not match the grouped replay")
    seen_groups: set[str] = set()
    normalized_groups: list[dict[str, Any]] = []
    for group_index, raw_group in enumerate(groups):
        path = f"packet.episode_groups[{group_index}]"
        group = require_object(raw_group, path)
        reject_unknown_fields(
            group,
            {"episode_group_id", "episode_identity_sha256", "partition", "probes"},
            path,
        )
        group_id = require_label(group.get("episode_group_id"), f"{path}.episode_group_id")
        if group_id in seen_groups:
            raise InputError("packet episode_group_id values must be unique")
        seen_groups.add(group_id)
        episode_identity = require_sha256(
            group.get("episode_identity_sha256"), f"{path}.episode_identity_sha256"
        )
        if group.get("partition") != "fit_only":
            raise InputError(f"{path}.partition must be fit_only at G0")
        probes = require_list(group.get("probes"), f"{path}.probes")
        if len(probes) != 3:
            raise InputError(f"{path}.probes must contain exactly three probes")
        normalized_probes: dict[str, dict[str, Any]] = {}
        query_hashes: set[str] = set()
        for probe_index, raw_probe in enumerate(probes):
            probe_path = f"{path}.probes[{probe_index}]"
            probe = require_object(raw_probe, probe_path)
            reject_unknown_fields(
                probe,
                {"probe_class", "query_sha256", "expected_target_set_sha256", "ranks"},
                probe_path,
            )
            probe_class = probe.get("probe_class")
            if probe_class not in PROBE_CLASSES or probe_class in normalized_probes:
                raise InputError(f"{path}.probes must contain exact, related, unrelated once")
            query_hash = require_sha256(
                probe.get("query_sha256"), f"{probe_path}.query_sha256"
            )
            if query_hash in query_hashes:
                raise InputError(f"{path} probe query hashes must be distinct")
            query_hashes.add(query_hash)
            normalized_probes[probe_class] = {
                "probe_class": probe_class,
                "query_sha256": query_hash,
                "expected_target_set_sha256": require_sha256(
                    probe.get("expected_target_set_sha256"),
                    f"{probe_path}.expected_target_set_sha256",
                ),
                "ranks": validate_ranks(
                    probe.get("ranks"), contract, f"{probe_path}.ranks"
                ),
            }
        if tuple(sorted(normalized_probes)) != tuple(sorted(PROBE_CLASSES)):
            raise InputError(f"{path} is missing a required probe class")
        target_sets = {
            probe["expected_target_set_sha256"] for probe in normalized_probes.values()
        }
        if len(target_sets) != 1:
            raise InputError(f"{path} probes must share one expected episode target set")
        normalized_groups.append(
            {
                "episode_group_id": group_id,
                "episode_identity_sha256": episode_identity,
                "partition": "fit_only",
                "probes": normalized_probes,
            }
        )

    return {
        "packet_id": packet_id,
        "evidence_class": evidence_class,
        "application": application,
        "provenance": provenance,
        "replay": normalized_replay,
        "episode_groups": normalized_groups,
    }


def best_rank(ranks: dict[str, int]) -> int:
    return min((rank for rank in ranks.values() if rank > 0), default=0)


def classify_group(group: dict[str, Any]) -> dict[str, Any]:
    exact_rank = best_rank(group["probes"]["exact"]["ranks"])
    related_rank = best_rank(group["probes"]["related"]["ranks"])
    unrelated_rank = best_rank(group["probes"]["unrelated"]["ranks"])
    exact_pass = exact_rank > 0
    related_pass = related_rank > 0
    unrelated_pass = unrelated_rank == 0
    if not exact_pass:
        signature = "ordinary_retrieval_gap"
    elif not related_pass and unrelated_pass:
        signature = "generalization_gap"
    elif related_pass and not unrelated_pass:
        signature = "overgeneralization_gap"
    elif related_pass and unrelated_pass:
        signature = "no_relevant_gap"
    else:
        signature = "ambiguous_dual_failure"
    return {
        "episode_group_id": group["episode_group_id"],
        "signature": signature,
        "exact_pass": exact_pass,
        "related_pass": related_pass,
        "unrelated_pass": unrelated_pass,
        "best_ranks": {
            "exact": exact_rank,
            "related": related_rank,
            "unrelated": unrelated_rank,
        },
    }


def evaluate_packet(
    packet_value: dict[str, Any], packet_raw: bytes, contract: dict[str, Any], contract_raw: bytes
) -> dict[str, Any]:
    packet = validate_packet(packet_value, contract)
    results = [classify_group(group) for group in packet["episode_groups"]]
    counts: dict[str, int] = {}
    for result in results:
        signature = result["signature"]
        counts[signature] = counts.get(signature, 0) + 1
    relevant_count = sum(counts.get(signature, 0) for signature in RELEVANT_SIGNATURES)

    blockers: list[str] = []
    provenance = packet["provenance"]
    if packet["evidence_class"] == "consumer_owned_real":
        if not provenance["consumer_owned"]:
            blockers.append("consumer_owned_false")
        if not provenance["observed_before_candidate_selection"]:
            blockers.append("not_observed_before_candidate_selection")
        if provenance["candidate_authored_probes"]:
            blockers.append("candidate_authored_probes")
        if not provenance["rights_cleared"]:
            blockers.append("rights_not_cleared")
        if provenance["source_identity_sha256"] == "0" * 64:
            blockers.append("source_identity_placeholder")
        if provenance["consumer_review_receipt_sha256"] == "0" * 64:
            blockers.append("consumer_review_receipt_placeholder")

    if packet["evidence_class"] == "synthetic_contract_test":
        verdict = "SYNTHETIC_ONLY_NO_ADMISSION"
        ready_for_g1 = False
    elif blockers:
        verdict = "BLOCKED_PROVENANCE"
        ready_for_g1 = False
    elif relevant_count >= contract["minimum_real_relevant_groups"]:
        verdict = "PASS_OBSERVED_RELEVANT_FAILURE"
        ready_for_g1 = True
    else:
        verdict = "NO_RELEVANT_FAILURE"
        ready_for_g1 = False

    return {
        "schema": RECEIPT_SCHEMA,
        "contract_id": contract["contract_id"],
        "contract_sha256": sha256_bytes(contract_raw),
        "packet_id": packet["packet_id"],
        "packet_sha256": sha256_bytes(packet_raw),
        "evidence_class": packet["evidence_class"],
        "application": packet["application"],
        "group_results": results,
        "signature_counts": dict(sorted(counts.items())),
        "relevant_group_count": relevant_count,
        "blockers": sorted(blockers),
        "g0_verdict": verdict,
        "ready_for_g1_grouped_corpus_design": ready_for_g1,
        "candidate_implementation_authority": False,
        "g1_corpus_freeze_authority": False,
        "retrieval_order_mutation_authority": False,
        "runtime_promotion_authority": False,
        "raw_content_in_receipt": False,
    }


def validate_private_spec(value: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    reject_unknown_fields(
        value,
        {
            "schema",
            "contract_id",
            "packet_id",
            "evidence_class",
            "application",
            "provenance",
            "baseline",
            "episode_groups",
        },
        "private_spec",
    )
    if value.get("schema") != PRIVATE_SPEC_SCHEMA:
        raise InputError(f"private_spec.schema must be {PRIVATE_SPEC_SCHEMA}")
    if value.get("contract_id") != contract["contract_id"]:
        raise InputError("private_spec.contract_id does not match the contract")
    packet_id = require_label(value.get("packet_id"), "private_spec.packet_id")
    evidence_class = value.get("evidence_class")
    if evidence_class not in EVIDENCE_CLASSES:
        raise InputError("private_spec.evidence_class is unsupported")
    application = validate_application(value.get("application"), "private_spec.application")
    provenance = validate_provenance(value.get("provenance"), "private_spec.provenance")

    baseline = require_object(value.get("baseline"), "private_spec.baseline")
    reject_unknown_fields(
        baseline,
        {
            "source_commit",
            "binary_sha256",
            "retrieval_modes",
            "top_k",
            "environment_sha256",
            "embedding_transport",
        },
        "private_spec.baseline",
    )
    normalized_baseline = {
        "source_commit": require_commit(
            baseline.get("source_commit"), "private_spec.baseline.source_commit"
        ),
        "binary_sha256": require_sha256(
            baseline.get("binary_sha256"),
            "private_spec.baseline.binary_sha256",
            nonzero=True,
        ),
        "retrieval_modes": unique_strings(
            baseline.get("retrieval_modes"),
            "private_spec.baseline.retrieval_modes",
            labels=True,
        ),
        "top_k": require_nonnegative_int(
            baseline.get("top_k"), "private_spec.baseline.top_k"
        ),
        "environment_sha256": require_sha256(
            baseline.get("environment_sha256"),
            "private_spec.baseline.environment_sha256",
            nonzero=True,
        ),
        "embedding_transport": baseline.get("embedding_transport"),
    }
    if normalized_baseline["retrieval_modes"] != contract["modes"]:
        raise InputError("private spec baseline modes drift from the contract")
    if normalized_baseline["top_k"] != contract["top_k"]:
        raise InputError("private spec top_k drifts from the contract")
    if normalized_baseline["embedding_transport"] not in {"local", "loopback_delegated"}:
        raise InputError("private spec embedding_transport is unsupported")

    groups = require_list(value.get("episode_groups"), "private_spec.episode_groups")
    if not groups:
        raise InputError("private_spec.episode_groups must not be empty")
    group_limit = (
        MAX_G0_EPISODE_GROUPS
        if evidence_class == "consumer_owned_real"
        else MAX_SYNTHETIC_EPISODE_GROUPS
    )
    if len(groups) > group_limit:
        raise InputError("private spec exceeds the bounded G0 episode-group limit")
    seen_groups: set[str] = set()
    normalized_groups: list[dict[str, Any]] = []
    for group_index, raw_group in enumerate(groups):
        path = f"private_spec.episode_groups[{group_index}]"
        group = require_object(raw_group, path)
        reject_unknown_fields(
            group,
            {"episode_group_id", "episode_identity_sha256", "partition", "probes"},
            path,
        )
        group_id = require_label(group.get("episode_group_id"), f"{path}.episode_group_id")
        if group_id in seen_groups:
            raise InputError("private spec episode_group_id values must be unique")
        seen_groups.add(group_id)
        if group.get("partition") != "fit_only":
            raise InputError(f"{path}.partition must be fit_only")
        probes = require_list(group.get("probes"), f"{path}.probes")
        if len(probes) != 3:
            raise InputError(f"{path}.probes must contain exactly three probes")
        normalized_probes: dict[str, dict[str, Any]] = {}
        query_hashes: set[str] = set()
        for probe_index, raw_probe in enumerate(probes):
            probe_path = f"{path}.probes[{probe_index}]"
            probe = require_object(raw_probe, probe_path)
            reject_unknown_fields(
                probe, {"probe_class", "query", "expected_target_keys"}, probe_path
            )
            probe_class = probe.get("probe_class")
            if probe_class not in PROBE_CLASSES or probe_class in normalized_probes:
                raise InputError(f"{path} must contain each probe class once")
            query = require_string(probe.get("query"), f"{probe_path}.query", max_bytes=8192)
            query_hash = sha256_text(query)
            if query_hash in query_hashes:
                raise InputError(f"{path} probe queries must be distinct")
            query_hashes.add(query_hash)
            expected_keys = unique_strings(
                probe.get("expected_target_keys"), f"{probe_path}.expected_target_keys"
            )
            if len(expected_keys) > MAX_EXPECTED_TARGET_KEYS:
                raise InputError(
                    f"{probe_path}.expected_target_keys exceeds the bounded target limit"
                )
            normalized_probes[probe_class] = {
                "probe_class": probe_class,
                "query": query,
                "query_sha256": query_hash,
                "expected_target_keys": expected_keys,
                "expected_target_set_sha256": sha256_canonical(sorted(expected_keys)),
            }
        target_sets = {
            probe["expected_target_set_sha256"] for probe in normalized_probes.values()
        }
        if len(target_sets) != 1:
            raise InputError(f"{path} probes must share one expected episode target set")
        normalized_groups.append(
            {
                "episode_group_id": group_id,
                "episode_identity_sha256": require_sha256(
                    group.get("episode_identity_sha256"),
                    f"{path}.episode_identity_sha256",
                ),
                "partition": "fit_only",
                "probes": normalized_probes,
            }
        )

    if evidence_class == "consumer_owned_real":
        if not provenance["consumer_owned"]:
            raise InputError("real private spec must be consumer-owned before replay")
        if not provenance["observed_before_candidate_selection"]:
            raise InputError("real failure must predate candidate selection")
        if provenance["candidate_authored_probes"]:
            raise InputError("candidate-authored probes cannot enter real replay")
        if not provenance["rights_cleared"]:
            raise InputError("real private spec lacks rights clearance")
        require_sha256(
            provenance["source_identity_sha256"],
            "private_spec.provenance.source_identity_sha256",
            nonzero=True,
        )
        require_sha256(
            provenance["consumer_review_receipt_sha256"],
            "private_spec.provenance.consumer_review_receipt_sha256",
            nonzero=True,
        )

    return {
        "packet_id": packet_id,
        "evidence_class": evidence_class,
        "application": application,
        "provenance": provenance,
        "baseline": normalized_baseline,
        "episode_groups": normalized_groups,
    }


def ensure_real_spec_is_private(path: Path, repo: Path) -> None:
    repo_root = repo.resolve()
    resolved = path.resolve()
    data_root = (repo_root / "data").resolve()
    if not data_root.is_relative_to(repo_root):
        raise InputError("repository data/ must not resolve outside the repository")
    if not resolved.is_relative_to(data_root):
        raise InputError("real intake spec must stay under the repository data/ tree")
    relative = resolved.relative_to(repo_root)
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", "--", str(relative)],
        cwd=repo,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if ignored.returncode != 0:
        raise InputError("real intake spec path is not ignored by git")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", str(relative)],
        cwd=repo,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if tracked.returncode == 0:
        raise InputError("real intake spec must not be tracked by git")
    if tracked.returncode != 1:
        raise InputError("could not prove real intake spec is untracked")


def parse_search_keys(text: str) -> list[str]:
    try:
        raw = json.loads(
            text,
            parse_constant=reject_json_constant,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except json.JSONDecodeError as exc:
        raise InputError("memory_search returned invalid nested JSON") from exc
    hits = require_list(raw, "memory_search hits")
    keys: list[str] = []
    for index, raw_hit in enumerate(hits):
        hit = require_object(raw_hit, f"memory_search hits[{index}]")
        record = hit.get("record", hit)
        record = require_object(record, f"memory_search hits[{index}].record")
        key = require_string(record.get("key"), f"memory_search hits[{index}].key", max_bytes=512)
        keys.append(key)
    return keys


def rank_expected(keys: list[str], expected: list[str]) -> int:
    ranks = [keys.index(key) + 1 for key in expected if key in keys]
    return min(ranks) if ranks else 0


def encode_sql_value(value: Any) -> bytes:
    if value is None:
        return b"N"
    if isinstance(value, int):
        return b"I" + str(value).encode("ascii")
    if isinstance(value, float):
        return b"F" + value.hex().encode("ascii")
    if isinstance(value, str):
        return b"S" + value.encode("utf-8")
    if isinstance(value, bytes):
        return b"B" + value
    raise InputError("durable SQLite table contains an unsupported value type")


def durable_content_index_state_sha256(db_path: Path) -> str:
    digest = hashlib.sha256()
    # SQLite online backup preserves the source's WAL journal-mode header but
    # intentionally does not leave WAL/SHM sidecars behind. ``immutable=1``
    # lets this audit read that closed, disposable snapshot without creating
    # sidecars or treating their absence as an I/O failure. A replay child can
    # leave valid WAL state behind, in which case the audit must include it.
    wal_path = Path(f"{db_path}-wal")
    uri_options = "?mode=ro" if wal_path.exists() else "?mode=ro&immutable=1"
    uri = db_path.resolve().as_uri() + uri_options
    connection = sqlite3.connect(uri, uri=True)
    current_table = "sqlite_master"
    try:
        connection.execute("PRAGMA query_only=ON")
        available = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        missing = set(DURABLE_CONTENT_INDEX_TABLES) - available
        if missing:
            raise InputError("snapshot is missing durable content/index tables")
        for table in DURABLE_CONTENT_INDEX_TABLES:
            current_table = table
            digest.update(table.encode("utf-8") + b"\0")
            quoted = '"' + table.replace('"', '""') + '"'
            schema_row = connection.execute(
                "SELECT type, sql FROM sqlite_master WHERE name = ?", (table,)
            ).fetchone()
            if schema_row is None:
                raise InputError("snapshot lost a durable content/index table")
            for value in schema_row:
                encoded = encode_sql_value(value)
                digest.update(len(encoded).to_bytes(8, "big"))
                digest.update(encoded)
            if table == "memories_fts":
                # Access-metadata updates fire the legacy AFTER UPDATE trigger,
                # which rewrites FTS5 shadow segments even though key/content
                # and query semantics stay identical. Audit the logical index
                # projection, not FTS5's disposable segment layout.
                selected_columns = ["rowid", "key", "content"]
                primary_key = [(1, "rowid")]
            else:
                columns = connection.execute(f"PRAGMA table_xinfo({quoted})").fetchall()
                primary_key = sorted(
                    (row[5], row[1])
                    for row in columns
                    if isinstance(row[5], int) and row[5] > 0
                )
                excluded = DURABLE_STATE_EXCLUDED_COLUMNS.get(table, set())
                selected_columns = [row[1] for row in columns if row[1] not in excluded]
            if not primary_key:
                raise InputError("durable table lacks a deterministic primary key")
            excluded = DURABLE_STATE_EXCLUDED_COLUMNS.get(table, set())
            if not selected_columns or any(name in excluded for _, name in primary_key):
                raise InputError("durable table projection excludes its identity")
            select_list = ", ".join(
                '"' + name.replace('"', '""') + '"' for name in selected_columns
            )
            for name in selected_columns:
                digest.update(name.encode("utf-8") + b"\0")
            order_by = ", ".join(
                '"' + name.replace('"', '""') + '"' for _, name in primary_key
            )
            rows = connection.execute(
                f"SELECT {select_list} FROM {quoted} ORDER BY {order_by}"
            )
            for row in rows:
                digest.update(b"R")
                for value in row:
                    encoded = encode_sql_value(value)
                    digest.update(len(encoded).to_bytes(8, "big"))
                    digest.update(encoded)
    except sqlite3.Error as exc:
        raise InputError(
            f"failed to fingerprint durable table {current_table}: {exc}"
        ) from exc
    finally:
        connection.close()
    return digest.hexdigest()


def sqlite_backup_read_only(source: Path, destination: Path) -> tuple[int, int]:
    source_uri = source.resolve().as_uri() + "?mode=ro"
    try:
        source_connection = sqlite3.connect(source_uri, uri=True)
        try:
            destination_connection = sqlite3.connect(destination)
            try:
                source_connection.execute("PRAGMA query_only=ON")
                changes_before = source_connection.total_changes
                source_connection.backup(destination_connection)
                changes_after = source_connection.total_changes
            finally:
                destination_connection.close()
        finally:
            source_connection.close()
    except sqlite3.Error as exc:
        raise InputError(f"read-only SQLite online backup failed: {exc}") from exc
    if changes_before != 0 or changes_after != 0:
        raise InputError("source SQLite connection recorded an unexpected write")
    return changes_before, changes_after


def clone_snapshot(source: Path, destination: Path) -> None:
    commands = []
    if sys.platform == "darwin":
        commands.append(["cp", "-c", str(source), str(destination)])
    else:
        commands.append(["cp", "--reflink=auto", str(source), str(destination)])
    for command in commands:
        completed = subprocess.run(command, capture_output=True, check=False, timeout=60)
        if completed.returncode == 0:
            return
    try:
        shutil.copy2(source, destination)
    except OSError as exc:
        raise InputError(f"failed to clone the frozen baseline snapshot: {exc}") from exc


def freeze_baseline_binary(
    source: Path, destination: Path, expected_sha256: str
) -> str:
    try:
        shutil.copy2(source, destination)
    except OSError as exc:
        raise InputError("failed to freeze the baseline binary") from exc
    if not destination.is_file() or not os.access(destination, os.X_OK):
        raise InputError("frozen baseline binary is not executable")
    observed_sha256 = sha256_file(destination)
    if observed_sha256 != expected_sha256:
        raise InputError("baseline binary SHA-256 does not match the private spec")
    return observed_sha256


def remove_observation_artifacts(snapshot: Path, stderr_path: Path) -> None:
    for path in [
        snapshot,
        Path(f"{snapshot}-wal"),
        Path(f"{snapshot}-shm"),
        Path(f"{snapshot}-journal"),
        stderr_path,
    ]:
        path.unlink(missing_ok=True)


def run_one_baseline_search(
    *,
    binary: Path,
    repo: Path,
    snapshot: Path,
    stderr_path: Path,
    timeout: float,
    query: str,
    mode: str,
    top_k: int,
    exclude_kinds: list[str],
    perception_filter_status: str,
    perception_filter_snapshot: Path | None,
) -> list[str]:
    overrides = {"AB_BIOCORTEX_RETRIEVAL_DISABLE": "1"}
    if perception_filter_status == "frozen":
        if perception_filter_snapshot is None:
            raise InputError("frozen perception-filter state lacks a snapshot")
        overrides["AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH"] = str(
            perception_filter_snapshot
        )
    elif perception_filter_status in {"absent", "disabled"}:
        overrides["AGENT_BRIDGE_SEED_BOOST_DISABLE"] = "1"
    else:
        raise InputError("unsupported perception-filter state")
    previous_environment = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    client: McpClient | None = None
    close_error: TrialError | None = None
    try:
        client = McpClient(binary, repo, snapshot, stderr_path, timeout)
        client.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "engram-g0-baseline-replay", "version": "0"},
            },
        )
        client.notify("notifications/initialized")
        result, _ = client.request(
            "tools/call",
            {
                "name": "memory_search",
                "arguments": {
                    "query": query,
                    "mode": mode,
                    "limit": top_k,
                    "exclude_kinds": exclude_kinds,
                },
            },
        )
        keys = parse_search_keys(mcp_text(result, "memory_search"))
    finally:
        if client is not None:
            try:
                client.close()
            except TrialError as exc:
                close_error = exc
        for key, previous in previous_environment.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
    if close_error is not None:
        raise close_error
    stderr = stderr_path.read_bytes()
    if str(snapshot).encode("utf-8") not in stderr:
        raise InputError("MCP child did not confirm its isolated snapshot path")
    return keys


def capture_packet(
    spec: dict[str, Any],
    contract: dict[str, Any],
    source_db: Path,
    binary: Path,
    repo: Path,
    timeout: float,
) -> dict[str, Any]:
    if not source_db.is_file():
        raise InputError("source SQLite database does not exist")
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise InputError("baseline binary must be an executable file")
    perception_state = observe_perception_filter_state()
    environment = baseline_environment_observation(contract, perception_state)
    if environment["environment_sha256"] != spec["baseline"]["environment_sha256"]:
        raise InputError("baseline environment SHA-256 does not match the private spec")
    if environment["embedding_transport"] != spec["baseline"]["embedding_transport"]:
        raise InputError("baseline embedding transport does not match the private spec")

    with tempfile.TemporaryDirectory(prefix="ab-engram-g0-") as temp:
        temp_dir = Path(temp)
        frozen_binary = temp_dir / "agent-bridge.baseline"
        observed_binary_sha = freeze_baseline_binary(
            binary, frozen_binary, spec["baseline"]["binary_sha256"]
        )
        observe_binary_identity(
            frozen_binary, repo, spec["baseline"]["source_commit"], timeout
        )
        perception_snapshot = freeze_perception_filter_state(perception_state, temp_dir)
        base_snapshot = temp_dir / "state.base.db"
        source_changes_before, source_changes_after = sqlite_backup_read_only(
            source_db, base_snapshot
        )
        base_snapshot_before = sha256_file(base_snapshot)
        durable_before = durable_content_index_state_sha256(base_snapshot)
        captured_groups: list[dict[str, Any]] = []
        observation_index = 0
        for group in spec["episode_groups"]:
            captured_probes: list[dict[str, Any]] = []
            for probe_class in PROBE_CLASSES:
                probe = group["probes"][probe_class]
                ranks: dict[str, int] = {}
                for mode in contract["modes"]:
                    observation_index += 1
                    run_snapshot = temp_dir / f"state.run.{observation_index}.db"
                    stderr_path = temp_dir / f"mcp.{observation_index}.stderr.log"
                    clone_snapshot(base_snapshot, run_snapshot)
                    if sha256_file(run_snapshot) != base_snapshot_before:
                        raise InputError(
                            "an observation clone did not start from the frozen base"
                        )
                    keys = run_one_baseline_search(
                        binary=frozen_binary,
                        repo=repo,
                        snapshot=run_snapshot,
                        stderr_path=stderr_path,
                        timeout=timeout,
                        query=probe["query"],
                        mode=mode,
                        top_k=contract["top_k"],
                        exclude_kinds=contract["exclude_kinds"],
                        perception_filter_status=perception_state["status"],
                        perception_filter_snapshot=perception_snapshot,
                    )
                    ranks[mode] = rank_expected(keys, probe["expected_target_keys"])
                    durable_after = durable_content_index_state_sha256(run_snapshot)
                    if durable_after != durable_before:
                        raise InputError(
                            "an isolated search changed durable content/index state"
                        )
                    remove_observation_artifacts(run_snapshot, stderr_path)
                captured_probes.append(
                    {
                        "probe_class": probe_class,
                        "query_sha256": probe["query_sha256"],
                        "expected_target_set_sha256": probe[
                            "expected_target_set_sha256"
                        ],
                        "ranks": ranks,
                    }
                )
            captured_groups.append(
                {
                    "episode_group_id": group["episode_group_id"],
                    "episode_identity_sha256": group["episode_identity_sha256"],
                    "partition": "fit_only",
                    "probes": captured_probes,
                }
            )
        base_snapshot_after = sha256_file(base_snapshot)
        if base_snapshot_before != base_snapshot_after:
            raise InputError("frozen base snapshot changed during isolated replay")

    return {
        "schema": PACKET_SCHEMA,
        "contract_id": contract["contract_id"],
        "packet_id": spec["packet_id"],
        "evidence_class": spec["evidence_class"],
        "application": spec["application"],
        "provenance": spec["provenance"],
        "replay": {
            "baseline_source_commit": spec["baseline"]["source_commit"],
            "baseline_binary_sha256": observed_binary_sha,
            "baseline_environment_sha256": environment["environment_sha256"],
            "embedding_transport": environment["embedding_transport"],
            "perception_filter_state_status": environment[
                "perception_filter_state_status"
            ],
            "perception_filter_state_sha256": environment[
                "perception_filter_state_sha256"
            ],
            "baseline_modes": contract["modes"],
            "top_k": contract["top_k"],
            "traffic_class": "eval",
            "source_db_access_mode": "ro",
            "source_db_query_only": True,
            "source_db_total_changes_before": source_changes_before,
            "source_db_total_changes_after": source_changes_after,
            "base_snapshot_sha256_before": base_snapshot_before,
            "base_snapshot_sha256_after": base_snapshot_after,
            "base_snapshot_unchanged": True,
            "fresh_snapshot_per_probe_mode": True,
            "all_observation_snapshots_started_from_base": True,
            "durable_content_index_state_sha256_before": durable_before,
            "durable_content_index_state_sha256_after": durable_before,
            "durable_content_index_state_unchanged": True,
            "disposable_baseline_side_effects_confined": True,
            "baseline_observation_count": observation_index,
            "live_memory_writes": 0,
            "candidate_retrieval_order_mutations": 0,
            "outcome_collector_enabled": False,
            "candidate_mechanism_enabled": False,
        },
        "episode_groups": captured_groups,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-contract")
    validate.add_argument("--contract", required=True)
    validate.add_argument("--pretty", action="store_true")

    fingerprint = subparsers.add_parser("fingerprint-environment")
    fingerprint.add_argument("--contract", required=True)
    fingerprint.add_argument("--pretty", action="store_true")

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--contract", required=True)
    evaluate.add_argument("--packet", required=True)
    evaluate.add_argument("--require-g1-ready", action="store_true")
    evaluate.add_argument("--pretty", action="store_true")

    capture = subparsers.add_parser("capture")
    capture.add_argument("--contract", required=True)
    capture.add_argument("--private-spec", required=True)
    capture.add_argument("--source-db", required=True)
    capture.add_argument("--agent-bridge-bin", required=True)
    capture.add_argument("--repo", required=True)
    capture.add_argument("--timeout-secs", type=float, default=120.0)
    capture.add_argument("--require-g1-ready", action="store_true")
    capture.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        contract_value, contract_raw = read_json(Path(args.contract))
        contract = validate_contract(contract_value)
        if args.command == "validate-contract":
            output = {
                "schema": CONTRACT_RECEIPT_SCHEMA,
                "contract_id": contract["contract_id"],
                "contract_sha256": sha256_bytes(contract_raw),
                "verdict": "PASS",
                "candidate_implementation_authority": False,
            }
            ready = False
        elif args.command == "fingerprint-environment":
            perception_state = observe_perception_filter_state()
            environment = baseline_environment_observation(contract, perception_state)
            output = {
                "schema": BASELINE_ENV_RECEIPT_SCHEMA,
                "contract_id": contract["contract_id"],
                "baseline_environment_sha256": environment["environment_sha256"],
                "embedding_transport": environment["embedding_transport"],
                "perception_filter_state_status": environment[
                    "perception_filter_state_status"
                ],
                "perception_filter_state_sha256": environment[
                    "perception_filter_state_sha256"
                ],
                "raw_environment_values_emitted": False,
                "candidate_implementation_authority": False,
            }
            ready = False
        elif args.command == "evaluate":
            packet_value, packet_raw = read_json(Path(args.packet))
            output = evaluate_packet(packet_value, packet_raw, contract, contract_raw)
            ready = output["ready_for_g1_grouped_corpus_design"]
        else:
            if not math.isfinite(args.timeout_secs) or args.timeout_secs <= 0:
                raise InputError("--timeout-secs must be positive and finite")
            spec_path = Path(args.private_spec)
            spec_value, _ = read_json(spec_path)
            spec = validate_private_spec(spec_value, contract)
            repo = Path(args.repo).resolve()
            if not repo.is_dir():
                raise InputError("--repo must name an existing directory")
            if spec["evidence_class"] == "consumer_owned_real":
                ensure_real_spec_is_private(spec_path, repo)
            packet = capture_packet(
                spec,
                contract,
                Path(args.source_db),
                Path(args.agent_bridge_bin),
                repo,
                args.timeout_secs,
            )
            packet_raw = render_json(packet).encode("utf-8")
            receipt = evaluate_packet(packet, packet_raw, contract, contract_raw)
            output = {"packet": packet, "receipt": receipt}
            ready = receipt["ready_for_g1_grouped_corpus_design"]
    except (InputError, TrialError, OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (KeyError, TypeError, IndexError):
        print("ERROR: malformed G0 input", file=sys.stderr)
        return 2

    print(render_json(output, pretty=args.pretty))
    if getattr(args, "require_g1_ready", False) and not ready:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
