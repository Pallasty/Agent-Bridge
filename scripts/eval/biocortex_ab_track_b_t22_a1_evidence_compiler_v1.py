"""Fail-closed signed-event and terminal-evidence compiler for T22-A1.

The compiler accepts already collected in-memory private artifacts, replays all
three fixed-command receipt chains, verifies every source-domain SSHSIG, builds
the canonical coordinator event chain, scans exact bootstrap secrets, and
returns a schema-valid terminal evidence value.  It performs no network,
listener, process, fault, provider, or persistent-output action.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_executor_core_v1.py"
CHALLENGE_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_collection_challenge_v1.py"
TRANSPORT_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_mtls_transport_v1.py"
EVENT_SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-distributed-event-schema-v1.json"
TERMINAL_SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-terminal-evidence-schema-v1.json"
EXPECTED_EVENT_SCHEMA_SHA256 = "4aaad4ea4006cfbae80fc784837146f3de48bcf9655fd1fe30a237f0d34f6cf5"
EXPECTED_TERMINAL_SCHEMA_SHA256 = "f3e6b833b04150376d09f3926dc75601acced248ebd9f9e08d70a86cc51e2a1a"
DOMAIN_EVENT_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-event-payload/v1\0"
OBSERVATION_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/observation/v1\0"
EVENT_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/distributed-event/v1\0"
LOG_SET_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/owned-process-log-set/v1\0"
TERMINAL_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/terminal-evidence/v1\0"
SIGNATURE_NAMESPACE = "agent-bridge-t22-a1-domain-event-v1"
DOMAIN_IDS = ("domain-1", "domain-2", "domain-3")
ZERO_SHA256 = "0" * 64
MAX_EVENT_BYTES = 256 * 1024
MAX_SIGNATURE_BYTES = 64 * 1024
MAX_LOG_BYTES = 4 * 1024 * 1024
MAX_LOG_SET_BYTES = 16 * 1024 * 1024
EVIDENCE_ACTIVATION_READY = False

# Global order is deliberately fixed. Multiple event claims may bind the same
# command receipt, but every source-domain payload remains independently signed.
EVENT_PLAN = (
    ("domain-1", "PREFLIGHT", "EXECUTION_PREFLIGHT_ACCEPTED"),
    ("domain-2", "PREFLIGHT", "EXECUTION_PREFLIGHT_ACCEPTED"),
    ("domain-3", "PREFLIGHT", "EXECUTION_PREFLIGHT_ACCEPTED"),
    ("domain-1", "START_OWNED_CLUSTER_MEMBERS", "DOMAIN_PROCESS_STARTED"),
    ("domain-2", "START_OWNED_CLUSTER_MEMBERS", "DOMAIN_PROCESS_STARTED"),
    ("domain-3", "START_OWNED_CLUSTER_MEMBERS", "DOMAIN_PROCESS_STARTED"),
    ("domain-1", "QUERY_CLUSTER_STATE", "ETCD_CLUSTER_READY"),
    ("domain-1", "QUERY_CLUSTER_STATE", "OPENBAO_CLUSTER_READY"),
    ("domain-1", "EXECUTE_AUTHORIZE_CONSUME", "LINEARIZABLE_AUTHORIZE_CONSUME_OBSERVED"),
    ("domain-1", "EXECUTE_AUTHORIZE_CONSUME", "REPLAY_CONSUME_REJECTED"),
    ("domain-1", "CREATE_PREFAULT_TRANSIT_SIGNATURE", "PREFAULT_TRANSIT_SIGNATURE_CREATED"),
    ("FAULT_TARGET", "STOP_OWNED_SERVICE_SET", "FAULT_TARGET_OWNED_SERVICES_STOPPED"),
    ("SURVIVOR_PARTICIPANT", "VERIFY_SURVIVING_QUORUM_AND_STATE", "SURVIVING_TWO_DOMAIN_ETCD_QUORUM_OBSERVED"),
    ("SURVIVOR_PARTICIPANT", "VERIFY_SURVIVING_QUORUM_AND_STATE", "SURVIVING_TWO_DOMAIN_OPENBAO_AVAILABLE"),
    ("domain-1", "VERIFY_POSTFAULT_TRANSIT_SIGNATURE", "POSTFAULT_TRANSIT_SIGNATURE_VERIFIED"),
    ("FAULT_TARGET", "RESTART_OWNED_SERVICE_SET", "FAULT_TARGET_OWNED_SERVICES_RESTARTED"),
    ("SURVIVOR_PARTICIPANT", "CLEANUP_OWNED_PROCESSES", "DOMAIN_CLEANUP_COMPLETE"),
    ("FAULT_TARGET", "VERIFY_TARGET_REJOIN", "FAULT_TARGET_REJOINED"),
    ("domain-1", "CLEANUP_OWNED_PROCESSES", "DOMAIN_CLEANUP_COMPLETE"),
    ("FAULT_TARGET", "CLEANUP_OWNED_PROCESSES", "DOMAIN_CLEANUP_COMPLETE"),
    ("domain-1", "TERMINAL_STATUS", "EXECUTION_TERMINALIZED"),
)

EXPECTED_LOG_NAMES = (
    "etcd.stderr.log", "etcd.stdout.log", "openbao.stderr.log", "openbao.stdout.log",
)


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def load_module(name: str, source: Path):
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_executor_module():
    return load_module("t22a1_executor_for_evidence", EXECUTOR_SOURCE)


def load_challenge_module():
    return load_module("t22a1_challenge_for_evidence", CHALLENGE_SOURCE)


def load_transport_module():
    return load_module("t22a1_transport_for_evidence", TRANSPORT_SOURCE)


def no_float(value: object) -> bool:
    if isinstance(value, float):
        return False
    if isinstance(value, dict):
        return all(isinstance(key, str) and no_float(item) for key, item in value.items())
    if isinstance(value, list):
        return all(no_float(item) for item in value)
    return True


def canonical(value: object) -> bytes:
    require(no_float(value), "E_EVIDENCE_FLOAT_FORBIDDEN")
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(domain: bytes, value: object) -> str:
    return hashlib.sha256(domain + canonical(value)).hexdigest()


def is_sha256(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and value != ZERO_SHA256
        and all(character in "0123456789abcdef" for character in value)
    )


def parse_time(value: object, code: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise SafeFailure(code) from error
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0, code)
    return parsed


def load_validators() -> tuple[Draft202012Validator, Draft202012Validator]:
    event_raw = EVENT_SCHEMA_PATH.read_bytes()
    terminal_raw = TERMINAL_SCHEMA_PATH.read_bytes()
    require(hashlib.sha256(event_raw).hexdigest() == EXPECTED_EVENT_SCHEMA_SHA256, "E_EVIDENCE_EVENT_SCHEMA_DIGEST")
    require(hashlib.sha256(terminal_raw).hexdigest() == EXPECTED_TERMINAL_SCHEMA_SHA256, "E_EVIDENCE_TERMINAL_SCHEMA_DIGEST")
    try:
        event_schema = json.loads(event_raw)
        terminal_schema = json.loads(terminal_raw)
        Draft202012Validator.check_schema(event_schema)
        Draft202012Validator.check_schema(terminal_schema)
    except Exception as error:
        raise SafeFailure("E_EVIDENCE_SCHEMA_INVALID") from error
    return (
        Draft202012Validator(event_schema, format_checker=FormatChecker()),
        Draft202012Validator(terminal_schema, format_checker=FormatChecker()),
    )


def canonical_public_key(raw: bytes, expected_sha256: str) -> bytes:
    require(isinstance(raw, bytes) and 0 < len(raw) <= 16 * 1024, "E_EVIDENCE_DOMAIN_PUBLIC_KEY")
    challenge = load_challenge_module()
    try:
        value = challenge.canonical_public_key_bytes(raw)
    except RuntimeError as error:
        raise SafeFailure(str(error)) from error
    require(hashlib.sha256(value).hexdigest() == expected_sha256, "E_EVIDENCE_DOMAIN_PUBLIC_KEY_BINDING")
    return value


def verify_signature(
    payload_raw: bytes,
    signature_raw: bytes,
    public_key: bytes,
    domain_id: str,
    executable_path: str,
    executable_sha256: str,
) -> str:
    require(0 < len(signature_raw) <= MAX_SIGNATURE_BYTES, "E_EVIDENCE_SIGNATURE_SIZE")
    executable = Path(executable_path)
    require(executable.is_absolute() and executable.is_file() and not executable.is_symlink(), "E_EVIDENCE_SSH_KEYGEN")
    metadata = executable.stat()
    require(stat.S_ISREG(metadata.st_mode) and 0 < metadata.st_size <= 64 * 1024 * 1024, "E_EVIDENCE_SSH_KEYGEN")
    require(hashlib.sha256(executable.read_bytes()).hexdigest() == executable_sha256, "E_EVIDENCE_SSH_KEYGEN_DIGEST")
    with tempfile.TemporaryDirectory(prefix="t22-a1-evidence-signature-") as directory:
        root = Path(directory)
        allowed = root / "allowed_signers"
        signature = root / "event.sshsig"
        allowed.write_bytes(domain_id.encode() + b" " + public_key)
        signature.write_bytes(signature_raw)
        allowed.chmod(0o600)
        signature.chmod(0o600)
        result = subprocess.run(
            [str(executable), "-Y", "verify", "-f", str(allowed), "-I", domain_id,
             "-n", SIGNATURE_NAMESPACE, "-s", str(signature)],
            input=payload_raw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={"LANG": "C", "LC_ALL": "C"}, check=False,
        )
    require(result.returncode == 0, "E_EVIDENCE_DOMAIN_EVENT_SIGNATURE")
    return hashlib.sha256(signature_raw).hexdigest()


def observation_sha256(observation: dict) -> str:
    return digest(OBSERVATION_DOMAIN, observation)


def build_domain_event_payload(
    receipt: dict,
    event_type: str,
    domain_sequence: int,
    previous_domain_event_sha256: str,
    attestation_packet_sha256: str,
    domain_public_key_sha256: str,
) -> dict:
    require(event_type in {row[2] for row in EVENT_PLAN}, "E_EVIDENCE_DOMAIN_EVENT_TYPE")
    require(isinstance(domain_sequence, int) and domain_sequence >= 0, "E_EVIDENCE_DOMAIN_SEQUENCE")
    require(
        (domain_sequence == 0 and previous_domain_event_sha256 == ZERO_SHA256)
        or (domain_sequence > 0 and is_sha256(previous_domain_event_sha256)),
        "E_EVIDENCE_DOMAIN_PREVIOUS",
    )
    require(is_sha256(attestation_packet_sha256) and is_sha256(domain_public_key_sha256), "E_EVIDENCE_DOMAIN_BINDING")
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_event_payload.v1",
        "packet_kind": "T22_A1_PRIVATE_SIGNED_SOURCE_DOMAIN_EVENT",
        "run_id": receipt["run_id"],
        "source_commit": receipt["source_commit"],
        "execution_contract_sha256": receipt["execution_contract_sha256"],
        "domain_id": receipt["domain_id"],
        "domain_sequence": domain_sequence,
        "previous_domain_event_sha256": previous_domain_event_sha256,
        "event_type": event_type,
        "command": receipt["command"],
        "command_receipt_sha256": receipt["content_sha256"],
        "observation_sha256": observation_sha256(receipt["observation"]),
        "attestation_packet_sha256": attestation_packet_sha256,
        "domain_public_key_sha256": domain_public_key_sha256,
        "observed_at": receipt["observed_at"],
        "contains_raw_endpoint": False,
        "contains_secret_material": False,
        "production_admissible": False,
    }
    value["content_sha256"] = digest(DOMAIN_EVENT_DOMAIN, value)
    return value


def decode_domain_event(raw: bytes) -> dict:
    require(0 < len(raw) <= MAX_EVENT_BYTES and raw.endswith(b"\n") and raw.count(b"\n") == 1, "E_EVIDENCE_DOMAIN_EVENT_FRAMING")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SafeFailure("E_EVIDENCE_DOMAIN_EVENT_JSON") from error
    require(isinstance(value, dict) and raw == canonical(value) + b"\n", "E_EVIDENCE_DOMAIN_EVENT_CANONICAL")
    required = {
        "schema", "packet_kind", "run_id", "source_commit", "execution_contract_sha256",
        "domain_id", "domain_sequence", "previous_domain_event_sha256", "event_type",
        "command", "command_receipt_sha256", "observation_sha256",
        "attestation_packet_sha256", "domain_public_key_sha256", "observed_at",
        "contains_raw_endpoint", "contains_secret_material", "production_admissible",
        "content_sha256",
    }
    require(set(value) == required, "E_EVIDENCE_DOMAIN_EVENT_SHAPE")
    require(value["schema"] == "agent_bridge.biocortex.track_b.t22_a1.domain_event_payload.v1", "E_EVIDENCE_DOMAIN_EVENT_SCHEMA")
    require(value["packet_kind"] == "T22_A1_PRIVATE_SIGNED_SOURCE_DOMAIN_EVENT", "E_EVIDENCE_DOMAIN_EVENT_KIND")
    require(value["contains_raw_endpoint"] is False and value["contains_secret_material"] is False, "E_EVIDENCE_DOMAIN_EVENT_BOUNDARY")
    require(value["production_admissible"] is False, "E_EVIDENCE_DOMAIN_EVENT_CLAIMS")
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256")
    require(claimed == digest(DOMAIN_EVENT_DOMAIN, unsigned), "E_EVIDENCE_DOMAIN_EVENT_DIGEST")
    return value


def resolve_event_plan(fault_target: str) -> tuple[tuple[str, str, str], ...]:
    require(fault_target in {"domain-2", "domain-3"}, "E_EVIDENCE_FAULT_TARGET")
    survivor = "domain-2" if fault_target == "domain-3" else "domain-3"
    return tuple(
        (fault_target if domain_id == "FAULT_TARGET" else survivor if domain_id == "SURVIVOR_PARTICIPANT" else domain_id, command, event_type)
        for domain_id, command, event_type in EVENT_PLAN
    )


def validate_coordinator_chain(
    events: object,
    execution: dict,
    validator: Draft202012Validator | None = None,
) -> str:
    require(isinstance(events, list) and len(events) == len(EVENT_PLAN), "E_EVIDENCE_COORDINATOR_EVENT_SET")
    if validator is None:
        validator, _terminal_validator = load_validators()
    expected_plan = resolve_event_plan(execution["fault"]["target_domain_id"])
    previous = ZERO_SHA256
    previous_time: datetime | None = None
    for sequence, (event, expected) in enumerate(zip(events, expected_plan, strict=True)):
        require(isinstance(event, dict) and not list(validator.iter_errors(event)), "E_EVIDENCE_DISTRIBUTED_EVENT_SCHEMA")
        domain_id, _command, event_type = expected
        require(
            event["run_id"] == execution["run_id"]
            and event["source_commit"] == execution["source_commit"]
            and event["execution_contract_sha256"] == execution["content_sha256"],
            "E_EVIDENCE_COORDINATOR_EVENT_RUN",
        )
        require(
            event["sequence"] == sequence and event["previous_event_sha256"] == previous,
            "E_EVIDENCE_COORDINATOR_EVENT_CHAIN",
        )
        require(
            event["source_domain_id"] == domain_id and event["event_type"] == event_type,
            "E_EVIDENCE_COORDINATOR_EVENT_PLAN",
        )
        observed_at = parse_time(event["observed_at"], "E_EVIDENCE_EVENT_TIME")
        require(previous_time is None or previous_time <= observed_at, "E_EVIDENCE_EVENT_TIME_ORDER")
        previous_time = observed_at
        unsigned = dict(event)
        claimed = unsigned.pop("event_sha256")
        require(claimed == digest(EVENT_DOMAIN, unsigned), "E_EVIDENCE_COORDINATOR_EVENT_DIGEST")
        previous = claimed
    return previous


def validate_terminal_value(
    value: object,
    execution: dict,
    expected_event_count: int,
    expected_event_head_sha256: str,
    validator: Draft202012Validator | None = None,
) -> dict:
    if validator is None:
        _event_validator, validator = load_validators()
    require(isinstance(value, dict) and not list(validator.iter_errors(value)), "E_EVIDENCE_TERMINAL_SCHEMA")
    assert isinstance(value, dict)
    require(
        value["run_id"] == execution["run_id"]
        and value["source_commit"] == execution["source_commit"]
        and value["bindings"]["execution_contract_sha256"] == execution["content_sha256"],
        "E_EVIDENCE_TERMINAL_RUN",
    )
    require(
        value["event_chain"]["event_count"] == expected_event_count
        and value["event_chain"]["event_chain_head_sha256"] == expected_event_head_sha256,
        "E_EVIDENCE_TERMINAL_EVENT_BINDING",
    )
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256")
    require(claimed == digest(TERMINAL_DOMAIN, unsigned), "E_EVIDENCE_TERMINAL_DIGEST")
    return value


def validate_plan_and_receipts(execution: dict, plans: list[dict], receipt_chains: dict[str, list[dict]]) -> tuple[dict[str, dict], dict[str, dict], bool]:
    require([plan.get("domain_id") for plan in plans] == list(DOMAIN_IDS), "E_EVIDENCE_PLAN_SET")
    require(set(receipt_chains) == set(DOMAIN_IDS), "E_EVIDENCE_RECEIPT_SET")
    executor = load_executor_module()
    plan_module = executor.load_plan_module()
    summaries: dict[str, dict] = {}
    receipts_by_command: dict[str, dict] = {}
    synthetic_values: set[bool] = set()
    for plan in plans:
        unsigned = dict(plan)
        claimed = unsigned.pop("content_sha256", None)
        require(claimed == plan_module.digest(unsigned), "E_EVIDENCE_PLAN_DIGEST")
        require(plan["run_id"] == execution["run_id"] and plan["source_commit"] == execution["source_commit"], "E_EVIDENCE_PLAN_RUN")
        require(plan["bindings"]["execution_contract_sha256"] == execution["content_sha256"], "E_EVIDENCE_PLAN_EXECUTION")
        domain_id = plan["domain_id"]
        try:
            summaries[domain_id] = executor.validate_receipt_chain(receipt_chains[domain_id], plan)
        except RuntimeError as error:
            raise SafeFailure(str(error)) from error
        commands = [row["command"] for row in receipt_chains[domain_id]]
        require(len(commands) == len(set(commands)), "E_EVIDENCE_DUPLICATE_COMMAND")
        for receipt in receipt_chains[domain_id]:
            receipts_by_command[f"{domain_id}:{receipt['command']}"] = receipt
            synthetic_values.add(receipt["synthetic_backend"])
    require(len(synthetic_values) == 1, "E_EVIDENCE_MIXED_BACKEND")
    return summaries, receipts_by_command, synthetic_values.pop()


def validate_log_sets(log_sets: dict[str, list[dict]], receipts: dict[str, dict]) -> tuple[dict[str, str], list[bytes]]:
    require(set(log_sets) == set(DOMAIN_IDS), "E_EVIDENCE_LOG_DOMAIN_SET")
    digests: dict[str, str] = {}
    raw_values: list[bytes] = []
    for domain_id in DOMAIN_IDS:
        rows = log_sets[domain_id]
        require(isinstance(rows, list) and [row.get("name") for row in rows] == list(EXPECTED_LOG_NAMES), "E_EVIDENCE_LOG_SET")
        manifest = []
        total = 0
        for row in rows:
            require(set(row) == {"name", "raw"} and isinstance(row["raw"], bytes), "E_EVIDENCE_LOG_ROW")
            raw = row["raw"]
            require(len(raw) <= MAX_LOG_BYTES, "E_EVIDENCE_LOG_SIZE")
            total += len(raw)
            manifest.append({"name": row["name"], "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
            raw_values.append(raw)
        require(total <= MAX_LOG_SET_BYTES, "E_EVIDENCE_LOG_SET_SIZE")
        value = digest(LOG_SET_DOMAIN, {"domain_id": domain_id, "logs": manifest})
        cleanup = receipts[f"{domain_id}:CLEANUP_OWNED_PROCESSES"]["observation"]
        require(cleanup["owned_process_log_set_sha256"] == value, "E_EVIDENCE_LOG_SET_BINDING")
        require(cleanup["owned_process_log_count"] == len(rows), "E_EVIDENCE_LOG_COUNT")
        digests[domain_id] = value
    return digests, raw_values


def validate_secret_scan(secret_values: list[bytearray], scan_values: list[bytes], receipts: dict[str, dict], fault_target: str) -> None:
    require(isinstance(secret_values, list) and len(secret_values) == 1, "E_EVIDENCE_SECRET_SET")
    transport = load_transport_module()
    observed_hashes: set[str] = set()
    for domain_id in DOMAIN_IDS:
        observed_hashes.add(receipts[f"{domain_id}:START_OWNED_CLUSTER_MEMBERS"]["observation"]["secret_frame_sha256"])
    observed_hashes.add(receipts[f"{fault_target}:RESTART_OWNED_SERVICE_SET"]["observation"]["secret_frame_sha256"])
    expected_hashes: set[str] = set()
    try:
        secret_bytes = []
        for secret in secret_values:
            require(isinstance(secret, bytearray) and 16 <= len(secret) <= transport.MAX_SECRET_BYTES, "E_EVIDENCE_SECRET_VALUE")
            raw = bytes(secret)
            require(raw not in secret_bytes, "E_EVIDENCE_SECRET_REUSE")
            secret_bytes.append(raw)
            expected_hashes.add(hashlib.sha256(transport.encode_secret_frame(secret)).hexdigest())
        require(observed_hashes == expected_hashes, "E_EVIDENCE_SECRET_FRAME_BINDING")
        require(all(secret not in value for secret in secret_bytes for value in scan_values), "E_EVIDENCE_SECRET_VALUE_LEAK")
    finally:
        for secret in secret_values:
            if isinstance(secret, bytearray):
                secret[:] = b"\0" * len(secret)


def compile_terminal_evidence(
    execution: dict,
    admission: dict,
    plans: list[dict],
    receipt_chains: dict[str, list[dict]],
    signed_events: list[dict],
    domain_public_keys: dict[str, bytes],
    log_sets: dict[str, list[dict]],
    secret_values: list[bytearray],
    maximum_observed_clock_skew_seconds: int,
    synthetic_only: bool,
) -> dict:
    """Return terminal evidence plus coordinator events; persist nothing.

    Ownership of ``secret_values`` transfers to this function. Every bytearray
    is zeroized on either success or failure once secret validation begins.
    """
    event_validator, terminal_validator = load_validators()
    require(isinstance(execution, dict) and is_sha256(execution.get("content_sha256")), "E_EVIDENCE_EXECUTION")
    require(
        admission.get("status") == "AUTHORIZED_T22_A1_EXACT_OWNER_SIGNED_NONPRODUCTION_EXECUTION_ADMISSION"
        and admission.get("run_id") == execution["run_id"]
        and admission.get("source_commit") == execution["source_commit"]
        and admission.get("execution_contract_sha256") == execution["content_sha256"]
        and is_sha256(admission.get("content_sha256")),
        "E_EVIDENCE_ADMISSION",
    )
    summaries, receipts, observed_synthetic = validate_plan_and_receipts(execution, plans, receipt_chains)
    require(observed_synthetic is synthetic_only, "E_EVIDENCE_SYNTHETIC_DECLARATION")
    require(synthetic_only or EVIDENCE_ACTIVATION_READY, "E_EVIDENCE_ACTIVATION_NOT_READY")
    require(set(domain_public_keys) == set(DOMAIN_IDS), "E_EVIDENCE_DOMAIN_PUBLIC_KEY_SET")
    bindings = {row["domain_id"]: row for row in execution["admission_bindings"]["domain_bindings"]}
    require(set(bindings) == set(DOMAIN_IDS), "E_EVIDENCE_DOMAIN_BINDING_SET")
    public_keys = {
        domain_id: canonical_public_key(domain_public_keys[domain_id], bindings[domain_id]["domain_public_key_sha256"])
        for domain_id in DOMAIN_IDS
    }
    log_digests, log_raw_values = validate_log_sets(log_sets, receipts)
    event_plan = resolve_event_plan(execution["fault"]["target_domain_id"])
    require(isinstance(signed_events, list) and len(signed_events) == len(event_plan), "E_EVIDENCE_SIGNED_EVENT_SET")
    tool_path = execution["private_runtime"]["credential_verifier_ssh_keygen_executable_path"]
    tool_sha256 = execution["private_runtime"]["credential_verifier_ssh_keygen_executable_sha256"]
    domain_sequences = {domain_id: 0 for domain_id in DOMAIN_IDS}
    domain_heads = {domain_id: ZERO_SHA256 for domain_id in DOMAIN_IDS}
    domain_counts = {domain_id: 0 for domain_id in DOMAIN_IDS}
    coordinator_events: list[dict] = []
    coordinator_previous = ZERO_SHA256
    prior_time: datetime | None = None
    payload_raw_values: list[bytes] = []
    signature_raw_values: list[bytes] = []
    for sequence, ((domain_id, command, event_type), signed) in enumerate(zip(event_plan, signed_events, strict=True)):
        require(isinstance(signed, dict) and set(signed) == {"payload_raw", "signature_raw"}, "E_EVIDENCE_SIGNED_EVENT_SHAPE")
        payload_raw = signed["payload_raw"]
        signature_raw = signed["signature_raw"]
        require(isinstance(payload_raw, bytes) and isinstance(signature_raw, bytes), "E_EVIDENCE_SIGNED_EVENT_TYPE")
        payload = decode_domain_event(payload_raw)
        receipt = receipts[f"{domain_id}:{command}"]
        expected = build_domain_event_payload(
            receipt, event_type, domain_sequences[domain_id], domain_heads[domain_id],
            bindings[domain_id]["attestation_packet_sha256"], bindings[domain_id]["domain_public_key_sha256"],
        )
        require(payload == expected, "E_EVIDENCE_DOMAIN_EVENT_RECONSTRUCTION")
        signature_sha256 = verify_signature(
            payload_raw, signature_raw, public_keys[domain_id], domain_id, tool_path, tool_sha256,
        )
        observed_at = parse_time(payload["observed_at"], "E_EVIDENCE_EVENT_TIME")
        require(prior_time is None or prior_time <= observed_at, "E_EVIDENCE_EVENT_TIME_ORDER")
        prior_time = observed_at
        event = {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.distributed_event.v1",
            "run_id": execution["run_id"], "source_commit": execution["source_commit"],
            "execution_contract_sha256": execution["content_sha256"],
            "sequence": sequence, "previous_event_sha256": coordinator_previous,
            "observed_at": payload["observed_at"], "source_domain_id": domain_id,
            "event_type": event_type, "observation_sha256": payload["observation_sha256"],
            "source_domain_evidence": {
                "attestation_packet_sha256": payload["attestation_packet_sha256"],
                "domain_event_payload_sha256": payload["content_sha256"],
                "detached_signature_sha256": signature_sha256,
                "domain_public_key_sha256": payload["domain_public_key_sha256"],
                "signature_scheme": "OPENSSH_SSHSIG_ED25519",
                "signature_namespace": SIGNATURE_NAMESPACE,
                "signature_verified": True,
            },
            "contains_raw_endpoint": False, "contains_secret_material": False,
        }
        event["event_sha256"] = digest(EVENT_DOMAIN, event)
        require(not list(event_validator.iter_errors(event)), "E_EVIDENCE_DISTRIBUTED_EVENT_SCHEMA")
        coordinator_events.append(event)
        coordinator_previous = event["event_sha256"]
        domain_sequences[domain_id] += 1
        domain_heads[domain_id] = payload["content_sha256"]
        domain_counts[domain_id] += 1
        payload_raw_values.append(payload_raw)
        signature_raw_values.append(signature_raw)
    coordinator_previous = validate_coordinator_chain(coordinator_events, execution, event_validator)
    scan_values = [*log_raw_values, *payload_raw_values, *signature_raw_values]
    scan_values.extend(canonical(receipt) for chain in receipt_chains.values() for receipt in chain)
    validate_secret_scan(secret_values, scan_values, receipts, execution["fault"]["target_domain_id"])

    all_receipts = [receipt for chain in receipt_chains.values() for receipt in chain]
    started = min(parse_time(receipt["observed_at"], "E_EVIDENCE_RECEIPT_TIME") for receipt in all_receipts)
    completed = max(parse_time(receipt["observed_at"], "E_EVIDENCE_RECEIPT_TIME") for receipt in all_receipts)
    expires = parse_time(execution["expires_at"], "E_EVIDENCE_EXECUTION_EXPIRY")
    runtime_seconds = int((completed - started).total_seconds())
    signed_maximum = execution["authorization"]["maximum_runtime_seconds"]
    require(0 <= runtime_seconds <= signed_maximum and completed < expires, "E_EVIDENCE_RUNTIME")
    require(
        isinstance(maximum_observed_clock_skew_seconds, int)
        and 0 <= maximum_observed_clock_skew_seconds <= 300,
        "E_EVIDENCE_CLOCK_SKEW",
    )
    fault_target = execution["fault"]["target_domain_id"]
    survivor_ids = [domain_id for domain_id in DOMAIN_IDS if domain_id != fault_target]
    total_spend = sum(summaries[domain_id]["cumulative_spend_usd_cents"] for domain_id in DOMAIN_IDS)
    maximum_spend = execution["budget"]["maximum_spend_usd_cents"]
    require(total_spend <= maximum_spend, "E_EVIDENCE_SPEND")
    domain_rows = []
    for domain_id in DOMAIN_IDS:
        cleanup = receipts[f"{domain_id}:CLEANUP_OWNED_PROCESSES"]["observation"]
        domain_rows.append({
            "domain_id": domain_id,
            "attestation_packet_sha256": bindings[domain_id]["attestation_packet_sha256"],
            "attestation_signature_verified": True,
            "signed_event_chain_head_sha256": domain_heads[domain_id],
            "domain_event_count": domain_counts[domain_id],
            "domain_event_signatures_verified": True,
            "preflight_receipt_sha256": receipts[f"{domain_id}:PREFLIGHT"]["observation"]["preflight_receipt_sha256"],
            "process_receipt_sha256": receipts[f"{domain_id}:START_OWNED_CLUSTER_MEMBERS"]["observation"]["process_receipt_sha256"],
            "cleanup_receipt_sha256": cleanup["cleanup_receipt_sha256"],
            "owned_process_log_set_sha256": log_digests[domain_id],
            "owned_process_logs_hashed": True, "cleanup_receipt_verified": True,
            "all_owned_processes_stopped": cleanup["all_owned_processes_stopped"],
            "all_owned_ports_released": cleanup["all_owned_ports_released"],
            "secret_value_scan_passed": cleanup["secret_value_scan_passed"],
        })
    consume = receipts["domain-1:EXECUTE_AUTHORIZE_CONSUME"]["observation"]
    prefault = receipts["domain-1:CREATE_PREFAULT_TRANSIT_SIGNATURE"]["observation"]
    postfault = receipts["domain-1:VERIFY_POSTFAULT_TRANSIT_SIGNATURE"]["observation"]
    stop = receipts[f"{fault_target}:STOP_OWNED_SERVICE_SET"]["observation"]
    restart = receipts[f"{fault_target}:RESTART_OWNED_SERVICE_SET"]["observation"]
    rejoin = receipts[f"{fault_target}:VERIFY_TARGET_REJOIN"]["observation"]
    survivors = [receipts[f"{domain_id}:VERIFY_SURVIVING_QUORUM_AND_STATE"]["observation"] for domain_id in survivor_ids]
    terminal = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.terminal_evidence.v1",
        "packet_kind": "T22_A1_H_TERMINAL_EVIDENCE",
        "hashing_contract": {
            "hash_algorithm": "SHA-256", "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
            "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/terminal-evidence/v1",
            "hash_scope": "ENTIRE_PACKET_EXCEPT_CONTENT_SHA256", "self_hash_field": "content_sha256",
            "self_hash_field_excluded": True, "cross_field_semantic_validation_required": True,
        },
        "status": "PASS_T22_A1_THREE_HOST_OWNED_SERVICE_SET_LOSS_RECOVERY", "failure_code": None,
        "run_id": execution["run_id"], "source_commit": execution["source_commit"],
        "bindings": {
            "execution_contract_sha256": execution["content_sha256"],
            "owner_authorization_content_sha256": execution["content_sha256"],
            "admission_contract_sha256": execution["admission_bindings"]["admission_contract_sha256"],
            "owner_decision_proposal_sha256": execution["admission_bindings"]["owner_decision_proposal_sha256"],
            "exact_three_domain_attestation_packet_set_sha256": execution["admission_bindings"]["exact_three_domain_attestation_packet_set_sha256"],
            "peer_endpoint_set_sha256": execution["network"]["peer_endpoint_set_sha256"],
            "acl_policy_receipt_sha256": execution["network"]["acl_policy_receipt_sha256"],
        },
        "timing": {
            "started_at": started.isoformat().replace("+00:00", "Z"),
            "completed_at": completed.isoformat().replace("+00:00", "Z"),
            "runtime_seconds": runtime_seconds, "signed_maximum_runtime_seconds": signed_maximum,
            "runtime_within_signed_limit": True,
            "maximum_observed_clock_skew_seconds": maximum_observed_clock_skew_seconds,
            "clock_skew_within_bound": True,
        },
        "domains": domain_rows,
        "cluster_evidence": {
            "etcd_distinct_voter_domain_count": 3, "openbao_distinct_voter_domain_count": 3,
            "linearizable_authorize_consume_observed": consume["linearizable_authorize_consume_observed"],
            "replay_consume_rejected": consume["replay_consume_rejected"],
            "prefault_transit_signature_created": prefault["prefault_transit_signature_created"],
            "fault_target_domain_id": fault_target, "fault_target_was_non_coordinator": fault_target != "domain-1",
            "target_owned_service_set_stopped": stop["etcd_process_stopped"] and stop["openbao_process_stopped"],
            "surviving_two_domain_etcd_quorum_observed": all(row["surviving_two_domain_etcd_quorum_observed"] for row in survivors),
            "surviving_two_domain_openbao_available": all(row["surviving_two_domain_openbao_available"] for row in survivors),
            "postfault_transit_signature_verified": postfault["postfault_transit_signature_verified"],
            "target_owned_service_set_restarted": restart["etcd_process_restarted"] and restart["openbao_process_restarted"],
            "target_domain_rejoined": rejoin["target_etcd_rejoined"] and rejoin["target_openbao_rejoined"],
        },
        "event_chain": {
            "event_count": len(coordinator_events), "event_chain_head_sha256": coordinator_previous,
            "canonical_coordinator_hash_chain_verified": True,
            "all_source_domain_signatures_verified": True, "terminal_event_present": True,
        },
        "cleanup": {
            "all_owned_processes_stopped": all(row["all_owned_processes_stopped"] for row in domain_rows),
            "all_owned_ports_released": all(row["all_owned_ports_released"] for row in domain_rows),
            "all_domain_cleanup_receipts_verified": True, "secret_value_scan_passed": True,
            "host_global_network_mutated": False, "ambient_or_external_credentials_accessed": False,
            "public_listeners_created": False, "spend_usd_cents": total_spend,
            "signed_maximum_spend_usd_cents": maximum_spend, "spend_within_signed_limit": True,
        },
        "claims": {
            "maximum_claim": "THREE_DISTINCT_PHYSICAL_HOST_PLACEMENT_AND_ONE_HOST_SCOPED_OWNED_SERVICE_SET_LOSS_RECOVERY_NONPRODUCTION",
            "admissible_claim_earned": True, "host_power_loss_proved": False,
            "site_power_network_independence_proved": False, "storage_device_durability_proved": False,
            "provider_durability_proved": False, "external_anti_rollback_proved": False,
            "production_admissible": False,
        },
        "completed_at": completed.isoformat().replace("+00:00", "Z"),
    }
    terminal["content_sha256"] = digest(TERMINAL_DOMAIN, terminal)
    validate_terminal_value(
        terminal, execution, len(coordinator_events), coordinator_previous, terminal_validator,
    )
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.evidence_compilation_result.v0",
        "terminal_evidence": terminal, "coordinator_events": coordinator_events,
        "synthetic_only": synthetic_only, "persistent_outputs_created": 0,
        "network_accessed": False, "listeners_started": 0, "processes_started": 0,
        "faults_injected": 0, "production_admissible": False,
    }


def status() -> dict:
    load_validators()
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.evidence_compiler_status.v0",
        "status": "OFFLINE_SIGNED_EVENT_AND_TERMINAL_COMPILER_READY_PERSISTENT_WRITER_AND_ACTIVATION_ABSENT",
        "evidence_activation_ready": EVIDENCE_ACTIVATION_READY,
        "real_execution_or_receipt_inputs_read": 0, "real_domain_signatures_read": 0,
        "real_secret_values_read": 0, "persistent_outputs_created": 0,
        "network_accessed": False, "listeners_started": 0, "processes_started": 0,
        "services_started": 0, "faults_injected": 0, "spend_usd_cents": 0,
        "execution_authorized": False, "production_admissible": False,
    }


if __name__ == "__main__":
    print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
