"""Atomic private evidence-set writer for T22-A1.

The writer independently replays a completed in-memory compilation, rechecks
all source-domain signatures, reserves exactly one publication attempt, writes
to a private staging directory, and atomically publishes one closed evidence
set. A failed reserved attempt is terminal and cannot be retried in place.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPILER_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_evidence_compiler_v1.py"
MANIFEST_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/evidence-set-manifest/v1\0"
MAX_OUTPUT_FILE_BYTES = 4 * 1024 * 1024
EVIDENCE_WRITER_ACTIVATION_READY = False
_COMPILER_MODULE = None


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def foreign_call(function, *arguments, **keywords):  # noqa: ANN001, ANN002, ANN003
    try:
        return function(*arguments, **keywords)
    except RuntimeError as error:
        raise SafeFailure(str(error)) from error


def load_compiler_module():
    global _COMPILER_MODULE  # noqa: PLW0603
    if _COMPILER_MODULE is not None:
        return _COMPILER_MODULE
    spec = importlib.util.spec_from_file_location("t22a1_compiler_for_writer", COMPILER_SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _COMPILER_MODULE = module
    return _COMPILER_MODULE


def canonical(value: object) -> bytes:
    return load_compiler_module().canonical(value)


def ensure_private_directory(path: Path, create: bool) -> None:
    require(path.is_absolute() and not path.is_symlink(), "E_EVIDENCE_WRITER_PRIVATE_DIRECTORY")
    if create and not path.exists():
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
        path.chmod(0o700)
    require(
        path.is_dir() and not path.is_symlink()
        and path.stat().st_uid == os.geteuid()
        and stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
        "E_EVIDENCE_WRITER_PRIVATE_DIRECTORY",
    )


def write_private_file(path: Path, raw: bytes) -> None:
    require(
        path.is_absolute() and not path.exists() and not path.is_symlink()
        and 0 < len(raw) <= MAX_OUTPUT_FILE_BYTES,
        "E_EVIDENCE_WRITER_OUTPUT_FILE",
    )
    ensure_private_directory(path.parent, create=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        if path.exists() and path.is_file() and not path.is_symlink():
            path.unlink()
        raise


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def reserve_once(run_root: Path, execution_sha256: str) -> Path:
    reservation = run_root / ".evidence-set.publication-reserved.json"
    require(not reservation.exists() and not reservation.is_symlink(), "E_EVIDENCE_WRITER_RESERVATION_EXISTS")
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.evidence_set_publication_reservation.v1",
        "status": "EVIDENCE_SET_PUBLICATION_RESERVED_SINGLE_ATTEMPT",
        "execution_contract_sha256": execution_sha256,
        "automatic_retry_allowed": False, "production_admissible": False,
    }
    write_private_file(reservation, canonical(value) + b"\n")
    fsync_directory(run_root)
    return reservation


def source_relative_path(sequence: int, event: dict, suffix: str) -> Path:
    stem = f"{sequence:04d}-{event['source_domain_id']}-{event['event_type'].lower()}"
    return Path("source-domain-events") / f"{stem}.{suffix}"


def coordinator_relative_path(sequence: int, event: dict) -> Path:
    return Path("coordinator-events") / f"{sequence:04d}-{event['event_type'].lower()}.json"


def validate_inputs(
    execution: dict,
    compilation: dict,
    signed_events: list[dict],
    domain_public_keys: dict[str, bytes],
    synthetic_only: bool,
) -> None:
    compiler = load_compiler_module()
    require(
        isinstance(compilation, dict)
        and set(compilation) == {
            "schema", "terminal_evidence", "coordinator_events", "synthetic_only",
            "persistent_outputs_created", "network_accessed", "listeners_started",
            "processes_started", "faults_injected", "production_admissible",
        }
        and compilation.get("schema") == "agent_bridge.biocortex.track_b.t22_a1.evidence_compilation_result.v0"
        and compilation.get("synthetic_only") is synthetic_only
        and compilation.get("persistent_outputs_created") == 0
        and compilation.get("network_accessed") is False
        and compilation.get("listeners_started") == compilation.get("processes_started") == 0
        and compilation.get("faults_injected") == 0
        and compilation.get("production_admissible") is False,
        "E_EVIDENCE_WRITER_COMPILATION",
    )
    require(synthetic_only or EVIDENCE_WRITER_ACTIVATION_READY, "E_EVIDENCE_WRITER_ACTIVATION_NOT_READY")
    events = compilation.get("coordinator_events")
    terminal = compilation.get("terminal_evidence")
    head = foreign_call(compiler.validate_coordinator_chain, events, execution)
    foreign_call(compiler.validate_terminal_value, terminal, execution, len(events), head)
    require(isinstance(signed_events, list) and len(signed_events) == len(events), "E_EVIDENCE_WRITER_SOURCE_EVENT_SET")
    require(set(domain_public_keys) == set(compiler.DOMAIN_IDS), "E_EVIDENCE_WRITER_DOMAIN_KEY_SET")
    bindings = {row["domain_id"]: row for row in execution["admission_bindings"]["domain_bindings"]}
    public_keys = {
        domain_id: foreign_call(
            compiler.canonical_public_key,
            domain_public_keys[domain_id], bindings[domain_id]["domain_public_key_sha256"],
        )
        for domain_id in compiler.DOMAIN_IDS
    }
    tool_path = execution["private_runtime"]["credential_verifier_ssh_keygen_executable_path"]
    tool_sha256 = execution["private_runtime"]["credential_verifier_ssh_keygen_executable_sha256"]
    for event, signed in zip(events, signed_events, strict=True):
        require(isinstance(signed, dict) and set(signed) == {"payload_raw", "signature_raw"}, "E_EVIDENCE_WRITER_SOURCE_EVENT_SHAPE")
        payload_raw = signed["payload_raw"]
        signature_raw = signed["signature_raw"]
        require(isinstance(payload_raw, bytes) and isinstance(signature_raw, bytes), "E_EVIDENCE_WRITER_SOURCE_EVENT_TYPE")
        payload = foreign_call(compiler.decode_domain_event, payload_raw)
        source = event["source_domain_evidence"]
        require(
            payload["domain_id"] == event["source_domain_id"]
            and payload["event_type"] == event["event_type"]
            and payload["observation_sha256"] == event["observation_sha256"]
            and payload["content_sha256"] == source["domain_event_payload_sha256"],
            "E_EVIDENCE_WRITER_SOURCE_EVENT_BINDING",
        )
        observed_signature = foreign_call(
            compiler.verify_signature,
            payload_raw, signature_raw, public_keys[event["source_domain_id"]],
            event["source_domain_id"], tool_path, tool_sha256,
        )
        require(observed_signature == source["detached_signature_sha256"], "E_EVIDENCE_WRITER_SOURCE_SIGNATURE_BINDING")


def manifest_value(execution: dict, compilation: dict, rows: list[dict]) -> dict:
    events = compilation["coordinator_events"]
    terminal = compilation["terminal_evidence"]
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.evidence_set_manifest.v1",
        "packet_kind": "T22_A1_PRIVATE_ATOMIC_EVIDENCE_SET_MANIFEST",
        "run_id": execution["run_id"], "source_commit": execution["source_commit"],
        "execution_contract_sha256": execution["content_sha256"],
        "source_domain_signed_event_count": len(events),
        "coordinator_event_count": len(events),
        "coordinator_event_chain_head_sha256": events[-1]["event_sha256"],
        "terminal_evidence_content_sha256": terminal["content_sha256"],
        "artifact_file_count_excluding_manifest": len(rows), "artifact_files": rows,
        "all_files_owner_only": True, "single_publication_attempt_reserved": True,
        "automatic_retry_allowed": False, "raw_endpoint_or_secret_in_manifest": False,
        "production_admissible": False,
    }
    value["content_sha256"] = hashlib.sha256(MANIFEST_DOMAIN + canonical(value)).hexdigest()
    return value


def validate_manifest(value: object, execution: dict, expected_rows: list[dict], compilation: dict) -> dict:
    required = {
        "schema", "packet_kind", "run_id", "source_commit", "execution_contract_sha256",
        "source_domain_signed_event_count", "coordinator_event_count",
        "coordinator_event_chain_head_sha256", "terminal_evidence_content_sha256",
        "artifact_file_count_excluding_manifest", "artifact_files", "all_files_owner_only",
        "single_publication_attempt_reserved", "automatic_retry_allowed",
        "raw_endpoint_or_secret_in_manifest", "production_admissible", "content_sha256",
    }
    require(isinstance(value, dict) and set(value) == required, "E_EVIDENCE_WRITER_MANIFEST_SHAPE")
    assert isinstance(value, dict)
    require(value["schema"] == "agent_bridge.biocortex.track_b.t22_a1.evidence_set_manifest.v1", "E_EVIDENCE_WRITER_MANIFEST_SCHEMA")
    require(value["packet_kind"] == "T22_A1_PRIVATE_ATOMIC_EVIDENCE_SET_MANIFEST", "E_EVIDENCE_WRITER_MANIFEST_KIND")
    require(value["run_id"] == execution["run_id"] and value["source_commit"] == execution["source_commit"], "E_EVIDENCE_WRITER_MANIFEST_RUN")
    require(value["execution_contract_sha256"] == execution["content_sha256"], "E_EVIDENCE_WRITER_MANIFEST_EXECUTION")
    require(value["source_domain_signed_event_count"] == value["coordinator_event_count"] == len(compilation["coordinator_events"]), "E_EVIDENCE_WRITER_MANIFEST_COUNT")
    require(value["coordinator_event_chain_head_sha256"] == compilation["coordinator_events"][-1]["event_sha256"], "E_EVIDENCE_WRITER_MANIFEST_EVENT_HEAD")
    require(value["terminal_evidence_content_sha256"] == compilation["terminal_evidence"]["content_sha256"], "E_EVIDENCE_WRITER_MANIFEST_TERMINAL")
    require(value["artifact_file_count_excluding_manifest"] == len(expected_rows) and value["artifact_files"] == expected_rows, "E_EVIDENCE_WRITER_MANIFEST_FILES")
    require(value["all_files_owner_only"] is True and value["single_publication_attempt_reserved"] is True, "E_EVIDENCE_WRITER_MANIFEST_BOUNDARY")
    require(value["automatic_retry_allowed"] is False and value["raw_endpoint_or_secret_in_manifest"] is False, "E_EVIDENCE_WRITER_MANIFEST_BOUNDARY")
    require(value["production_admissible"] is False, "E_EVIDENCE_WRITER_MANIFEST_CLAIMS")
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256")
    require(claimed == hashlib.sha256(MANIFEST_DOMAIN + canonical(unsigned)).hexdigest(), "E_EVIDENCE_WRITER_MANIFEST_DIGEST")
    return value


def artifact_rows(root: Path, relative_paths: list[Path]) -> list[dict]:
    rows = []
    for relative in sorted(relative_paths, key=lambda path: path.as_posix()):
        path = root / relative
        require(path.is_file() and not path.is_symlink(), "E_EVIDENCE_WRITER_PERSISTED_FILE")
        metadata = path.stat()
        require(
            metadata.st_uid == os.geteuid() and metadata.st_mode & 0o077 == 0
            and 0 < metadata.st_size <= MAX_OUTPUT_FILE_BYTES,
            "E_EVIDENCE_WRITER_PERSISTED_FILE",
        )
        raw = path.read_bytes()
        rows.append({
            "relative_path": relative.as_posix(), "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    return rows


def read_canonical(path: Path, code: str) -> dict:
    raw = path.read_bytes()
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, code)
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SafeFailure(code) from error
    require(isinstance(value, dict) and raw == canonical(value) + b"\n", code)
    return value


def validate_persisted_set(
    evidence_set: Path,
    execution: dict,
    compilation: dict,
    signed_events: list[dict],
    domain_public_keys: dict[str, bytes],
    synthetic_only: bool,
) -> dict:
    ensure_private_directory(evidence_set, create=False)
    validate_inputs(execution, compilation, signed_events, domain_public_keys, synthetic_only)
    expected_relative: list[Path] = []
    persisted_events = []
    for sequence, (event, signed) in enumerate(zip(compilation["coordinator_events"], signed_events, strict=True)):
        payload_relative = source_relative_path(sequence, event, "event.json")
        signature_relative = source_relative_path(sequence, event, "event.sshsig")
        coordinator_relative = coordinator_relative_path(sequence, event)
        expected_relative.extend([payload_relative, signature_relative, coordinator_relative])
        require((evidence_set / payload_relative).read_bytes() == signed["payload_raw"], "E_EVIDENCE_WRITER_PERSISTED_SOURCE_PAYLOAD")
        require((evidence_set / signature_relative).read_bytes() == signed["signature_raw"], "E_EVIDENCE_WRITER_PERSISTED_SOURCE_SIGNATURE")
        persisted_events.append(read_canonical(evidence_set / coordinator_relative, "E_EVIDENCE_WRITER_PERSISTED_COORDINATOR_EVENT"))
    terminal_relative = Path("terminal-evidence.json")
    expected_relative.append(terminal_relative)
    terminal = read_canonical(evidence_set / terminal_relative, "E_EVIDENCE_WRITER_PERSISTED_TERMINAL")
    require(persisted_events == compilation["coordinator_events"], "E_EVIDENCE_WRITER_PERSISTED_COORDINATOR_SET")
    require(terminal == compilation["terminal_evidence"], "E_EVIDENCE_WRITER_PERSISTED_TERMINAL_BINDING")
    rows = artifact_rows(evidence_set, expected_relative)
    manifest_path = evidence_set / "evidence-manifest.json"
    manifest = read_canonical(manifest_path, "E_EVIDENCE_WRITER_PERSISTED_MANIFEST")
    validate_manifest(manifest, execution, rows, compilation)
    entries = list(evidence_set.rglob("*"))
    require(all(not path.is_symlink() for path in entries), "E_EVIDENCE_WRITER_PERSISTED_FILE_SET")
    actual_files = {path.relative_to(evidence_set).as_posix() for path in entries if path.is_file()}
    actual_directories = {path.relative_to(evidence_set).as_posix() for path in entries if path.is_dir()}
    require(actual_files == {row["relative_path"] for row in rows} | {"evidence-manifest.json"}, "E_EVIDENCE_WRITER_PERSISTED_FILE_SET")
    require(actual_directories == {"coordinator-events", "source-domain-events"}, "E_EVIDENCE_WRITER_PERSISTED_FILE_SET")
    return manifest


def persist_evidence_set(
    execution: dict,
    compilation: dict,
    signed_events: list[dict],
    domain_public_keys: dict[str, bytes],
    synthetic_only: bool,
) -> dict:
    validate_inputs(execution, compilation, signed_events, domain_public_keys, synthetic_only)
    run_root = Path(execution["artifact_scope"]["run_evidence_root"])
    ensure_private_directory(run_root, create=False)
    repository = ROOT.resolve()
    resolved_root = run_root.resolve(strict=True)
    require(repository not in (resolved_root, *resolved_root.parents), "E_EVIDENCE_WRITER_ROOT_SCOPE")
    evidence_set = run_root / "evidence-set"
    staging = run_root / f".evidence-set.staging-{execution['content_sha256'][:16]}"
    require(not evidence_set.exists() and not evidence_set.is_symlink(), "E_EVIDENCE_WRITER_OUTPUT_EXISTS")
    reserve_once(run_root, execution["content_sha256"])
    require(not staging.exists() and not staging.is_symlink(), "E_EVIDENCE_WRITER_STAGING_EXISTS")
    try:
        staging.mkdir(mode=0o700, exist_ok=False)
        staging.chmod(0o700)
        relative_paths: list[Path] = []
        for sequence, (event, signed) in enumerate(zip(compilation["coordinator_events"], signed_events, strict=True)):
            payload_relative = source_relative_path(sequence, event, "event.json")
            signature_relative = source_relative_path(sequence, event, "event.sshsig")
            coordinator_relative = coordinator_relative_path(sequence, event)
            write_private_file(staging / payload_relative, signed["payload_raw"])
            write_private_file(staging / signature_relative, signed["signature_raw"])
            write_private_file(staging / coordinator_relative, canonical(event) + b"\n")
            relative_paths.extend([payload_relative, signature_relative, coordinator_relative])
        terminal_relative = Path("terminal-evidence.json")
        write_private_file(staging / terminal_relative, canonical(compilation["terminal_evidence"]) + b"\n")
        relative_paths.append(terminal_relative)
        rows = artifact_rows(staging, relative_paths)
        manifest = manifest_value(execution, compilation, rows)
        validate_manifest(manifest, execution, rows, compilation)
        write_private_file(staging / "evidence-manifest.json", canonical(manifest) + b"\n")
        for directory in sorted(
            (path for path in staging.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts), reverse=True,
        ):
            fsync_directory(directory)
        fsync_directory(staging)
        require(not evidence_set.exists(), "E_EVIDENCE_WRITER_OUTPUT_EXISTS")
        staging.rename(evidence_set)
        fsync_directory(run_root)
        observed = validate_persisted_set(
            evidence_set, execution, compilation, signed_events, domain_public_keys, synthetic_only,
        )
        return {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.evidence_set_publication_receipt.v1",
            "status": "PASS_T22_A1_PRIVATE_EVIDENCE_SET_ATOMICALLY_PUBLISHED",
            "run_id": execution["run_id"], "source_commit": execution["source_commit"],
            "execution_contract_sha256": execution["content_sha256"],
            "evidence_manifest_content_sha256": observed["content_sha256"],
            "terminal_evidence_content_sha256": compilation["terminal_evidence"]["content_sha256"],
            "artifact_file_count_including_manifest": len(rows) + 1,
            "publication_reservation_created": True, "atomic_directory_publication_completed": True,
            "readback_and_signature_reverification_passed": True,
            "automatic_retry_allowed": False, "network_accessed": False,
            "listeners_started": 0, "processes_started": 0, "faults_injected": 0,
            "production_admissible": False,
        }
    except Exception as error:
        if staging.exists() and staging.is_dir() and not staging.is_symlink():
            shutil.rmtree(staging)
            fsync_directory(run_root)
        if isinstance(error, SafeFailure):
            raise
        raise SafeFailure("E_EVIDENCE_WRITER_LOCAL_IO") from error


def status() -> dict:
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.evidence_writer_status.v0",
        "status": "ATOMIC_PRIVATE_EVIDENCE_WRITER_READY_REAL_ACTIVATION_AND_RUNNER_INTEGRATION_ABSENT",
        "evidence_writer_activation_ready": EVIDENCE_WRITER_ACTIVATION_READY,
        "real_execution_or_signature_inputs_read": 0, "persistent_evidence_sets_created": 0,
        "network_accessed": False, "listeners_started": 0, "processes_started": 0,
        "services_started": 0, "faults_injected": 0, "spend_usd_cents": 0,
        "execution_authorized": False, "production_admissible": False,
    }


if __name__ == "__main__":
    print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
