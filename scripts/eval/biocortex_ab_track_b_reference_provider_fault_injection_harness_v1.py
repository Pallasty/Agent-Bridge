#!/usr/bin/env python3
"""Deterministic offline doubles for the Track B provider fault plan.

This module is intentionally pure: it performs no filesystem, network,
process, provider, credential, clock, random, generator, or sink I/O.  Its
rows are simulator evidence only and can never satisfy a managed-service or
owned-lab evidence locus.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any


CONTRACT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "experiment_preregistration.v1"
)
CONTRACT_SHA256 = "632dbf1d8202d94d6aef70d8b20c04050e647679da973d81afbe13d68344ad22"
HARNESS_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "offline_harness_configuration.v1"
)
RUN_ROW_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "offline_harness_run_row.v1"
)
SUITE_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "offline_harness_suite_receipt.v1"
)
HARNESS_MODE = "OFFLINE_DETERMINISTIC_DOUBLE_ONLY"
EVIDENCE_CLASS = "OFFLINE_DOUBLE_SIMULATION_ONLY_NOT_PROVIDER_OR_LAB_EVIDENCE"
STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_OFFLINE_HARNESS_V1_IMPLEMENTED_"
    "SYNTHETIC_ONLY_NO_PROVIDER_INVOCATION"
)
DECISION = "OFFLINE_HARNESS_PASS_PROVIDER_EXPERIMENT_REMAINS_BLOCKED"
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "AUTHORITY_AND_ADAPTER_CONTRACT"
)

MANAGED_TRACK = "MANAGED_SPANNER_CLOUD_KMS"
SELF_HOSTED_TRACK = "SELF_HOSTED_ETCD_OPENBAO"
SCHEDULE_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/schedule"
)
RUN_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/run"
)
NAMESPACE_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/namespace"
)
ZERO_SHA256 = "0" * 64
MESSAGE_HEX = (
    "0000005d6167656e742d6272696467652f62696f636f727465782d61622f747261636b2d62"
    "2f65787465726e616c2d61746f6d69632d6c6976652d6f75747075742f617574686f726974"
    "792d6465636973696f6e2d7369676e61747572652f76310000000000000020000102030405"
    "060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
)
MESSAGE = bytes.fromhex(MESSAGE_HEX)
MESSAGE_SHA256 = "f5dcb16eec00a302bf56c9cc681b5c09d598589c4c3e9ab2413b68c21f16982d"
TEST_SEED = bytes(range(32))


class HarnessError(ValueError):
    """Closed validation or deterministic simulation failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HarnessError(message)


def canonical_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                indent=2,
                separators=(",", ": "),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HarnessError(f"cannot encode canonical JSON: {exc}") from exc


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def _framed_hash(domain: str, *parts: str) -> str:
    framed = bytearray()
    for part in (domain, *parts):
        raw = part.encode("utf-8")
        framed.extend(len(raw).to_bytes(4, "big"))
        framed.extend(raw)
    return sha256_bytes(bytes(framed))


def _framed_hash_bytes(domain: str, *parts: bytes) -> str:
    framed = bytearray()
    domain_raw = domain.encode("utf-8")
    framed.extend(len(domain_raw).to_bytes(4, "big"))
    framed.extend(domain_raw)
    for part in parts:
        framed.extend(len(part).to_bytes(4, "big"))
        framed.extend(part)
    return sha256_bytes(bytes(framed))


def exact_keys(value: Any, expected: set[str], label: str) -> None:
    require(type(value) is dict, f"{label} must be an object")
    require(set(value) == expected, f"{label} fields drift")


def crc32c(raw: bytes) -> int:
    """Castagnoli CRC32C, reflected polynomial, independent of provider code."""

    crc = 0xFFFFFFFF
    for octet in raw:
        crc ^= octet
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


# Minimal deterministic Ed25519 reference arithmetic for an offline double.
# It is deliberately not production key handling or a provider substitute.
_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493


def _inv(value: int) -> int:
    return pow(value, _Q - 2, _Q)


_D = (-121665 * _inv(121666)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x & 1:
        x = _Q - x
    return x


_BY = (4 * _inv(5)) % _Q
_B = (_xrecover(_BY), _BY)


def _edwards(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = left
    x2, y2 = right
    product = (_D * x1 * x2 * y1 * y2) % _Q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + product) % _Q
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - product) % _Q
    return x3, y3


def _scalarmult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = (0, 1)
    addend = point
    value = scalar
    while value:
        if value & 1:
            result = _edwards(result, addend)
        addend = _edwards(addend, addend)
        value >>= 1
    return result


def _encodepoint(point: tuple[int, int]) -> bytes:
    x, y = point
    encoded = y | ((x & 1) << 255)
    return encoded.to_bytes(32, "little")


def _decodepoint(raw: bytes) -> tuple[int, int]:
    require(len(raw) == 32, "Ed25519 public key length drift")
    encoded = int.from_bytes(raw, "little")
    y = encoded & ((1 << 255) - 1)
    sign = encoded >> 255
    require(y < _Q, "Ed25519 public key y is noncanonical")
    x = _xrecover(y)
    require(not (x == 0 and sign == 1), "Ed25519 x=0 sign bit is noncanonical")
    if (x & 1) != sign:
        x = _Q - x
    require(0 <= x < _Q, "Ed25519 x coordinate is noncanonical")
    point = (x, y)
    require(
        (-x * x + y * y - 1 - _D * x * x * y * y) % _Q == 0,
        "Ed25519 point is not on the curve",
    )
    return point


def _hint(raw: bytes) -> int:
    return int.from_bytes(hashlib.sha512(raw).digest(), "little")


def ed25519_public_key(seed: bytes) -> bytes:
    require(len(seed) == 32, "test seed must be 32 bytes")
    digest = hashlib.sha512(seed).digest()
    scalar = 2**254 + sum(
        2**index * ((digest[index // 8] >> (index & 7)) & 1)
        for index in range(3, 254)
    )
    return _encodepoint(_scalarmult(_B, scalar))


def ed25519_sign(message: bytes, seed: bytes = TEST_SEED) -> bytes:
    public_key = ed25519_public_key(seed)
    digest = hashlib.sha512(seed).digest()
    scalar = 2**254 + sum(
        2**index * ((digest[index // 8] >> (index & 7)) & 1)
        for index in range(3, 254)
    )
    nonce = _hint(digest[32:] + message) % _L
    encoded_r = _encodepoint(_scalarmult(_B, nonce))
    challenge = _hint(encoded_r + public_key + message) % _L
    encoded_s = ((nonce + challenge * scalar) % _L).to_bytes(32, "little")
    return encoded_r + encoded_s


@lru_cache(maxsize=64)
def ed25519_verify(signature: bytes, message: bytes, public_key: bytes) -> bool:
    try:
        if len(signature) != 64 or len(public_key) != 32:
            return False
        point_r = _decodepoint(signature[:32])
        point_a = _decodepoint(public_key)
        scalar_s = int.from_bytes(signature[32:], "little")
        if scalar_s >= _L:
            return False
        identity = (0, 1)
        if point_r == identity or point_a == identity:
            return False
        if _scalarmult(point_r, _L) != identity or _scalarmult(point_a, _L) != identity:
            return False
        challenge = _hint(signature[:32] + public_key + message) % _L
        return _scalarmult(_B, scalar_s) == _edwards(
            point_r, _scalarmult(point_a, challenge)
        )
    except HarnessError:
        return False


PUBLIC_KEY = ed25519_public_key(TEST_SEED)
PUBLIC_KEY_HEX = PUBLIC_KEY.hex()
PUBLIC_KEY_SHA256 = sha256_bytes(PUBLIC_KEY)
TEST_SIGNATURE = ed25519_sign(MESSAGE)
TEST_SIGNATURE_SHA256 = sha256_bytes(TEST_SIGNATURE)


@dataclass
class SimulationState:
    authority: str = "EMPTY"
    outbox: str = "NONE"
    attempt: str = "NONE"
    receipt: str = "NONE"
    terminal_fence: str = "NONE"
    restore: str = "NOT_APPLICABLE"
    watch: str = "NOT_APPLICABLE"
    cache: str = "NOT_APPLICABLE"
    database_attempts: int = 0
    simulated_application_calls: int = 0
    simulated_processing_events: int = 0
    restarts: int = 0
    emitted_outputs: int = 0
    challenge_consumptions: int = 0
    logical_sink_reservations: int = 0
    prepared_operation_id: str = ZERO_SHA256
    prepared_request_sha256: str = ZERO_SHA256
    prepared_key_version: int = 0
    prepared_public_key_sha256: str = ZERO_SHA256
    prepared_message_sha256: str = ZERO_SHA256
    prepared_attempt_sequence: int = 0
    prepared_record_sha256: str = ZERO_SHA256
    attempt_consumed: bool = False
    call_binding_sha256: str = ZERO_SHA256
    processed_response_sha256: str = ZERO_SHA256
    validated_response_sha256: str = ZERO_SHA256
    validation_binding_sha256: str = ZERO_SHA256
    receipt_binding_sha256: str = ZERO_SHA256
    durable_operation_record_sha256: str = ZERO_SHA256
    durable_operation_revision: int = 0
    witness_record_sha256: str = ZERO_SHA256
    witness_generation: int = 0
    restore_cluster_id: str = "NOT_APPLICABLE"
    restore_incarnation_id: str = "NOT_APPLICABLE"
    restore_revision_floor: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)

    def event(self, name: str, **details: Any) -> None:
        self.events.append(
            {"sequence": len(self.events) + 1, "name": name, "details": details}
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "authority": self.authority,
            "outbox": self.outbox,
            "attempt": self.attempt,
            "receipt": self.receipt,
            "terminal_fence": self.terminal_fence,
            "restore": self.restore,
            "watch": self.watch,
            "cache": self.cache,
            "database_attempts": self.database_attempts,
            "simulated_application_calls": self.simulated_application_calls,
            "simulated_processing_events": self.simulated_processing_events,
            "restarts": self.restarts,
            "emitted_outputs": self.emitted_outputs,
            "challenge_consumptions": self.challenge_consumptions,
            "logical_sink_reservations": self.logical_sink_reservations,
            "prepared_operation_id": self.prepared_operation_id,
            "prepared_request_sha256": self.prepared_request_sha256,
            "prepared_key_version": self.prepared_key_version,
            "prepared_public_key_sha256": self.prepared_public_key_sha256,
            "prepared_message_sha256": self.prepared_message_sha256,
            "prepared_attempt_sequence": self.prepared_attempt_sequence,
            "prepared_record_sha256": self.prepared_record_sha256,
            "attempt_consumed": self.attempt_consumed,
            "call_binding_sha256": self.call_binding_sha256,
            "processed_response_sha256": self.processed_response_sha256,
            "validated_response_sha256": self.validated_response_sha256,
            "validation_binding_sha256": self.validation_binding_sha256,
            "receipt_binding_sha256": self.receipt_binding_sha256,
            "durable_operation_record_sha256": self.durable_operation_record_sha256,
            "durable_operation_revision": self.durable_operation_revision,
            "witness_record_sha256": self.witness_record_sha256,
            "witness_generation": self.witness_generation,
            "restore_cluster_id": self.restore_cluster_id,
            "restore_incarnation_id": self.restore_incarnation_id,
            "restore_revision_floor": self.restore_revision_floor,
        }


@dataclass(frozen=True)
class PreparedAttemptRecord:
    operation_id: str
    canonical_request_sha256: str
    exact_key_version: int
    public_key_pin_sha256: str
    message_sha256: str
    attempt_sequence: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "canonical_request_sha256": self.canonical_request_sha256,
            "exact_key_version": self.exact_key_version,
            "public_key_pin_sha256": self.public_key_pin_sha256,
            "message_sha256": self.message_sha256,
            "attempt_sequence": self.attempt_sequence,
        }


@dataclass
class OneShotFaultController:
    assignment_sha256: str
    case_id: str
    injection_cut: str
    injection_variant: str
    trigger_limit: int
    armed: bool = False
    candidate_started: bool = False
    trigger_count: int = 0

    def arm(self, state: SimulationState) -> None:
        require(not self.armed and not self.candidate_started, "fault controller re-armed")
        self.armed = True
        state.event(
            "ONE_SHOT_FAULT_CONTROLLER_ARMED",
            assignment_sha256=self.assignment_sha256,
            case_id=self.case_id,
            injection_cut=self.injection_cut,
            injection_variant=self.injection_variant,
            trigger_limit=self.trigger_limit,
        )

    def start_candidate(self, state: SimulationState) -> None:
        require(self.armed and not self.candidate_started, "candidate start ordering drift")
        self.candidate_started = True
        state.event(
            "CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM",
            assignment_sha256=self.assignment_sha256,
            case_id=self.case_id,
        )

    def trigger(
        self,
        state: SimulationState,
        cut_point: str,
        causal_binding_sha256: str,
    ) -> None:
        require(self.armed and self.candidate_started, "fault triggered before arm/start")
        require(self.trigger_limit == 1, "control case attempted a fault")
        require(cut_point == self.injection_cut, "fault cut-point drift")
        require(self.trigger_count == 0, "one-shot fault triggered more than once")
        require(
            type(causal_binding_sha256) is str
            and len(causal_binding_sha256) == 64
            and all(char in "0123456789abcdef" for char in causal_binding_sha256),
            "fault causal binding drift",
        )
        self.trigger_count = 1
        state.event(
            "ONE_SHOT_FAULT_TRIGGERED",
            case_id=self.case_id,
            injection_cut=self.injection_cut,
            injection_variant=self.injection_variant,
            trigger_count=self.trigger_count,
            causal_binding_sha256=causal_binding_sha256,
        )

    def finish(self, state: SimulationState) -> None:
        require(self.trigger_count == self.trigger_limit, "fault trigger cardinality drift")
        if self.trigger_limit == 0:
            state.event(
                "CONTROL_NO_FAULT_TRIGGERED",
                case_id=self.case_id,
                trigger_count=0,
            )


EXACT_KEY_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/"
    "exact-operation-key"
)
OPERATION_STATE_RECORD_FIELDS = frozenset({
    "record_kind",
    "operation_id",
    "authority",
    "outbox",
    "attempt",
    "attempt_consumed",
    "receipt",
    "challenge_consumptions",
    "logical_sink_reservations",
    "message_sha256",
    "exact_key_version",
    "public_key_pin_sha256",
    "prepared_record_sha256",
    "call_binding_sha256",
    "processed_response_sha256",
    "validated_response_sha256",
    "validation_binding_sha256",
    "receipt_binding_sha256",
    "terminal",
})
TRANSITION_ENVELOPE_FIELDS = frozenset({
    "phase",
    "store_kind",
    "operation_id",
    "operation_key",
    "consistency",
    "nested",
    "leased",
    "compare_record_sha256",
    "observed_record_sha256",
    "expected_mod_revision",
    "committed_record_sha256",
    "committed_revision",
    "top_level_revision",
    "mutation_count",
    "cas_result",
    "response_revision_source",
})


def _operation_state_record(
    operation_id: str,
    exact_key_version: int,
    *,
    authority: str,
    outbox: str,
    attempt: str = "NONE",
    attempt_consumed: bool = False,
    receipt: str = "NONE",
    challenge_consumptions: int,
    logical_sink_reservations: int,
    prepared_record_sha256: str = ZERO_SHA256,
    call_binding_sha256: str = ZERO_SHA256,
    processed_response_sha256: str = ZERO_SHA256,
    validated_response_sha256: str = ZERO_SHA256,
    validation_binding_sha256: str = ZERO_SHA256,
    receipt_binding_sha256: str = ZERO_SHA256,
    terminal: bool = False,
) -> dict[str, Any]:
    record = {
        "record_kind": "EXACT_OPERATION_RECORD",
        "operation_id": operation_id,
        "authority": authority,
        "outbox": outbox,
        "attempt": attempt,
        "attempt_consumed": attempt_consumed,
        "receipt": receipt,
        "challenge_consumptions": challenge_consumptions,
        "logical_sink_reservations": logical_sink_reservations,
        "message_sha256": MESSAGE_SHA256,
        "exact_key_version": exact_key_version,
        "public_key_pin_sha256": PUBLIC_KEY_SHA256,
        "prepared_record_sha256": prepared_record_sha256,
        "call_binding_sha256": call_binding_sha256,
        "processed_response_sha256": processed_response_sha256,
        "validated_response_sha256": validated_response_sha256,
        "validation_binding_sha256": validation_binding_sha256,
        "receipt_binding_sha256": receipt_binding_sha256,
        "terminal": terminal,
    }
    exact_keys(record, set(OPERATION_STATE_RECORD_FIELDS), "operation state record")
    return record


@dataclass
class ExactKeyCASDouble:
    operation_key: str
    record: dict[str, Any] | None = None
    revision: int = 0
    delayed_record: dict[str, Any] | None = None
    bare_absent_observed: bool = False
    fence_committed: bool = False

    @classmethod
    def for_run(cls, run_id: str) -> "ExactKeyCASDouble":
        return cls(_framed_hash(EXACT_KEY_DOMAIN, run_id))

    @staticmethod
    def operation_record(run_id: str, exact_key_version: int) -> dict[str, Any]:
        return _operation_state_record(
            run_id,
            exact_key_version,
            authority="AUTHORIZED_COMMITTED",
            outbox="SIGN_PENDING",
            challenge_consumptions=1,
            logical_sink_reservations=1,
        )

    def stage_delayed_commit(self, record: dict[str, Any]) -> None:
        require(self.record is None and self.delayed_record is None, "delayed commit already staged")
        self.delayed_record = json.loads(canonical_bytes(record))

    def commit_now(self, record: dict[str, Any]) -> None:
        require(self.record is None, "exact-key commit conflict")
        self.record = json.loads(canonical_bytes(record))
        self.revision += 1

    def exact_read(
        self,
        state: SimulationState,
        event_name: str,
        *,
        consistency: str,
        expected_kind: str | None = None,
    ) -> dict[str, Any] | None:
        observed = None if self.record is None else json.loads(canonical_bytes(self.record))
        observed_sha = ZERO_SHA256 if observed is None else sha256_value(observed)
        result = "ABSENT" if observed is None else observed["record_kind"]
        state.event(
            event_name,
            operation_key=self.operation_key,
            consistency=consistency,
            result=result,
            record_sha256=observed_sha,
            revision=self.revision,
            terminal=False if observed is None else observed["terminal"],
        )
        if expected_kind is not None:
            require(observed is not None and observed["record_kind"] == expected_kind, "exact read kind drift")
        if observed is None:
            self.bare_absent_observed = True
        return observed

    def cas_absent_to_terminal_fence(
        self,
        state: SimulationState,
        event_name: str,
        *,
        kind: str,
        consistency: str,
        operation_id: str,
        exact_key_version: int,
    ) -> None:
        require(self.bare_absent_observed, "terminal fence preceded bare absent read")
        require(self.record is None and not self.fence_committed, "terminal fence CAS conflict")
        fence = _operation_state_record(
            operation_id,
            exact_key_version,
            authority="FENCED_ABSENT",
            outbox="NONE",
            challenge_consumptions=0,
            logical_sink_reservations=0,
            terminal=True,
        )
        fence["record_kind"] = "TERMINAL_FENCE"
        self.record = fence
        self.revision += 1
        self.fence_committed = True
        _commit_exact_record_transition(
            state,
            kind,
            "TERMINAL_FENCE_COMMITTED",
            fence,
            event_name,
            operation_key=self.operation_key,
            consistency=consistency,
            compare_record_sha256=ZERO_SHA256,
            committed_record_sha256=sha256_value(fence),
            cas_result="APPLIED",
            revision=self.revision,
        )
        require(
            state.durable_operation_record_sha256 == sha256_value(fence)
            and state.durable_operation_revision == self.revision,
            "terminal fence transition/store tip drift",
        )

    def release_delayed_commit(self, state: SimulationState, event_name: str) -> None:
        require(self.delayed_record is not None, "no delayed commit to release")
        require(self.fence_committed and self.record is not None, "delayed commit released before fence")
        delayed_sha = sha256_value(self.delayed_record)
        current_sha = sha256_value(self.record)
        require(delayed_sha != current_sha, "delayed operation aliases terminal fence")
        state.event(
            event_name,
            operation_key=self.operation_key,
            compare_record_sha256=ZERO_SHA256,
            delayed_record_sha256=delayed_sha,
            observed_record_sha256=current_sha,
            cas_result="CONFLICT_NO_MUTATION",
            revision=self.revision,
        )
        self.delayed_record = None

    def apply_delayed_commit(
        self,
        state: SimulationState,
        event_name: str,
        *,
        kind: str,
    ) -> None:
        require(self.delayed_record is not None and self.record is None, "delayed commit cannot apply")
        self.record = self.delayed_record
        self.delayed_record = None
        self.revision += 1
        _commit_exact_record_transition(
            state,
            kind,
            "AUTHORITY_OUTBOX_COMMITTED",
            self.record,
            event_name,
            operation_key=self.operation_key,
            record_sha256=sha256_value(self.record),
            cas_result="APPLIED",
            revision=self.revision,
        )
        require(
            state.durable_operation_record_sha256 == sha256_value(self.record)
            and state.durable_operation_revision == self.revision,
            "delayed commit transition/store tip drift",
        )


WITNESS_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/"
    "external-restore-witness"
)
WITNESS_ACTOR_DOMAIN = "OUTSIDE_ETCD_SNAPSHOT_AND_RESTORE_DOUBLE"
WITNESS_FIELDS = {
    "domain",
    "authority_id",
    "prior_cluster_id",
    "prior_incarnation_id",
    "prior_revision_floor",
    "snapshot_sha256",
    "snapshot_revision",
    "new_cluster_id",
    "new_incarnation_id",
    "new_revision_floor",
    "bump_revision",
    "mark_compacted",
    "rebase_authorization_sha256",
    "previous_record_sha256",
    "generation",
}


@dataclass(frozen=True)
class ExternalWitnessRecord:
    domain: str
    authority_id: str
    prior_cluster_id: str
    prior_incarnation_id: str
    prior_revision_floor: int
    snapshot_sha256: str
    snapshot_revision: int
    new_cluster_id: str
    new_incarnation_id: str
    new_revision_floor: int
    bump_revision: int
    mark_compacted: bool
    rebase_authorization_sha256: str
    previous_record_sha256: str
    generation: int

    def as_dict(self) -> dict[str, Any]:
        result = {
            field_name: getattr(self, field_name)
            for field_name in ExternalWitnessRecord.__dataclass_fields__
        }
        require(set(result) == WITNESS_FIELDS, "witness record field drift")
        return result


@dataclass
class ExternalWitnessLedger:
    logical_cluster_lineage_id: str
    actor_domain: str = WITNESS_ACTOR_DOMAIN
    current_record: ExternalWitnessRecord | None = None
    available: bool = True
    authority_id: str | None = None

    @staticmethod
    def witness_key(authority_id: str, logical_cluster_lineage_id: str) -> str:
        return _framed_hash(
            f"{WITNESS_DOMAIN}/exact-key",
            authority_id,
            logical_cluster_lineage_id,
        )

    @property
    def current_key(self) -> str:
        return (
            ZERO_SHA256
            if self.authority_id is None
            else self.witness_key(
                self.authority_id,
                self.logical_cluster_lineage_id,
            )
        )

    def seed(self, record: ExternalWitnessRecord) -> None:
        require(self.current_record is None and self.authority_id is None, "witness ledger already seeded")
        self.current_record = record
        self.authority_id = record.authority_id

    @property
    def current_sha256(self) -> str:
        return ZERO_SHA256 if self.current_record is None else sha256_value(self.current_record.as_dict())

    @property
    def generation(self) -> int:
        return 0 if self.current_record is None else self.current_record.generation

    def _valid_candidate(self, candidate: ExternalWitnessRecord) -> tuple[bool, str]:
        value = candidate.as_dict()
        if candidate.domain != WITNESS_DOMAIN:
            return False, "DOMAIN_MISMATCH"
        if candidate.previous_record_sha256 != self.current_sha256:
            return False, "PREVIOUS_RECORD_SHA256_MISMATCH"
        if candidate.generation != self.generation + 1:
            return False, "GENERATION_MISMATCH"
        if candidate.new_cluster_id == candidate.prior_cluster_id:
            return False, "CLUSTER_ID_REUSED"
        if candidate.new_incarnation_id == candidate.prior_incarnation_id:
            return False, "INCARNATION_ID_REUSED"
        if not candidate.mark_compacted:
            return False, "MARK_COMPACTED_REQUIRED"
        if candidate.bump_revision <= 0:
            return False, "POSITIVE_BUMP_REQUIRED"
        if candidate.new_revision_floor != candidate.snapshot_revision + candidate.bump_revision:
            return False, "REVISION_BINDING_MISMATCH"
        if candidate.new_revision_floor <= candidate.prior_revision_floor:
            return False, "REVISION_FLOOR_NOT_ADVANCED"
        for field_name in ("snapshot_sha256", "rebase_authorization_sha256", "previous_record_sha256"):
            raw = value[field_name]
            if type(raw) is not str or len(raw) != 64 or any(char not in "0123456789abcdef" for char in raw):
                return False, f"{field_name.upper()}_SHAPE"
        return True, "VALID"

    def compare_and_swap(
        self,
        state: SimulationState,
        candidate: ExternalWitnessRecord,
        *,
        caller_actor_domain: str,
        expected_previous_record_sha256: str,
        expected_generation: int,
        event_name: str,
    ) -> bool:
        observed_previous = self.current_sha256
        observed_generation = self.generation
        valid, reason = self._valid_candidate(candidate)
        cas_match = (
            expected_previous_record_sha256 == observed_previous
            and expected_generation == observed_generation
        )
        actor_authorized = caller_actor_domain == self.actor_domain
        candidate_key = self.witness_key(
            candidate.authority_id,
            self.logical_cluster_lineage_id,
        )
        observed_key = (
            candidate_key if self.authority_id is None else self.current_key
        )
        key_match = self.current_key in {ZERO_SHA256, candidate_key}
        applied = self.available and actor_authorized and valid and cas_match and key_match
        if applied:
            self.current_record = candidate
            self.authority_id = candidate.authority_id
        state.event(
            event_name,
            actor_domain=self.actor_domain,
            caller_actor_domain=caller_actor_domain,
            logical_cluster_lineage_id=self.logical_cluster_lineage_id,
            witness_key=candidate_key,
            observed_witness_key=observed_key,
            witness_record=candidate.as_dict(),
            witness_record_sha256=sha256_value(candidate.as_dict()),
            expected_previous_record_sha256=expected_previous_record_sha256,
            observed_previous_record_sha256=observed_previous,
            expected_generation=expected_generation,
            observed_generation=observed_generation,
            cas_result="APPLIED" if applied else "REJECTED_NO_MUTATION",
            rejection_reason=(
                "NONE"
                if applied
                else (
                    "UNAVAILABLE"
                    if not self.available
                    else "ACTOR_DOMAIN_FORBIDDEN"
                    if not actor_authorized
                    else "WITNESS_KEY_MISMATCH"
                    if not key_match
                    else reason
                    if not valid
                    else "CAS_COMPARE_MISMATCH"
                )
            ),
        )
        if applied:
            state.witness_record_sha256 = self.current_sha256
            state.witness_generation = self.generation
        return applied


@dataclass(frozen=True)
class S12ExecutionCorrelation:
    target_node: str
    route_node: str
    executing_node: str | None
    executing_ha_role: str | None
    cluster_id: str
    request_id: str
    redirect_node: str | None
    forwarded_by_node: str | None
    audit_record_sha256: str | None
    wire_attempt_sha256: str | None
    redirect_forward_audit_bound: bool

    def validate(self, *, success: bool) -> None:
        require(self.target_node and self.route_node and self.cluster_id and self.request_id, "S12 correlation identity missing")
        if success:
            require(self.executing_node is not None, "S12 success lacks executor")
            require(self.route_node != self.executing_node, "S12 route node equals executor")
            require(self.target_node != self.executing_node, "S12 sealed target executed request")
            require(self.executing_ha_role == "PERFORMANCE_STANDBY_ACTIVE", "S12 executor HA role drift")
            require(self.redirect_node == self.executing_node, "S12 redirect target drift")
            require(self.forwarded_by_node == self.route_node, "S12 forwarder drift")
            require(
                self.audit_record_sha256 is not None
                and len(self.audit_record_sha256) == 64
                and self.wire_attempt_sha256 is not None
                and len(self.wire_attempt_sha256) == 64,
                "S12 raw correlation hashes missing",
            )
            require(self.redirect_forward_audit_bound is True, "S12 redirect/forward audit missing")
        else:
            require(self.executing_node is None, "S12 failure preclaims an executor")
            require(self.executing_ha_role is None, "S12 failure preclaims an HA role")
            require(self.redirect_node is None, "S12 failure preclaims a redirect target")
            require(self.forwarded_by_node is None, "S12 failure preclaims a forwarder")
            require(self.audit_record_sha256 is None, "S12 failure preclaims an audit record")
            require(self.wire_attempt_sha256 is None, "S12 failure preclaims a wire attempt")
            require(self.redirect_forward_audit_bound is False, "S12 failure claims a completed audit")

    def event_details(self) -> dict[str, Any]:
        return {
            "target_node": self.target_node,
            "route_node": self.route_node,
            "executing_node": self.executing_node,
            "executing_ha_role": self.executing_ha_role,
            "cluster_id": self.cluster_id,
            "request_id": self.request_id,
            "redirect_node": self.redirect_node,
            "forwarded_by_node": self.forwarded_by_node,
            "audit_record_sha256": self.audit_record_sha256,
            "wire_attempt_sha256": self.wire_attempt_sha256,
            "redirect_forward_audit_bound": self.redirect_forward_audit_bound,
        }


@dataclass(frozen=True)
class ScheduleEntry:
    track_id: str
    case_id: str
    repetition_index: int
    block_position: int
    assignment_sha256: str
    configuration_sha256: str
    run_id: str
    namespace_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "case_id": self.case_id,
            "repetition_index": self.repetition_index,
            "block_position": self.block_position,
            "assignment_sha256": self.assignment_sha256,
            "configuration_sha256": self.configuration_sha256,
            "simulation_run_id": self.run_id,
            "namespace_id": self.namespace_id,
            "assignment_before_candidate_start": True,
            "injection_armed_before_candidate_start": True,
        }


BOUNDARY = {
    "condition_output_authorized": False,
    "cost_authority_bound": False,
    "credentials_accessed": False,
    "experiment_executed": False,
    "live_generator_in_scope": False,
    "live_output_permit_defined": False,
    "paid_resources_provisioned": False,
    "production_adapter_in_scope": False,
    "provider_called": False,
    "receipt_is_output_permit": False,
    "side_effects_unlocked": "NONE",
}


def validate_configuration(configuration: Any) -> None:
    exact_keys(
        configuration,
        {"schema", "mode", "deterministic_seed", "profiles", "boundary"},
        "configuration",
    )
    require(configuration["schema"] == HARNESS_SCHEMA, "configuration schema drift")
    require(configuration["mode"] == HARNESS_MODE, "configuration mode drift")
    seed = configuration["deterministic_seed"]
    require(type(seed) is str and len(seed) == 64, "deterministic seed shape drift")
    require(all(char in "0123456789abcdef" for char in seed), "seed is not lower hex")
    require(configuration["boundary"] == BOUNDARY, "configuration boundary drift")

    profiles = configuration["profiles"]
    exact_keys(profiles, {"managed", "self_hosted"}, "profiles")
    managed = profiles["managed"]
    exact_keys(
        managed,
        {
            "database_kind",
            "effective_isolation",
            "hidden_provider_retries",
            "kms_kind",
            "exact_key_version_resource",
            "key_version",
            "algorithm",
            "key_state",
            "protection_level",
            "public_key_hex",
        },
        "managed profile",
    )
    require(managed["database_kind"] == "IN_MEMORY_SPANNER_PROTOCOL_DOUBLE", "managed database double drift")
    require(managed["effective_isolation"] == "SERIALIZABLE", "managed isolation drift")
    require(managed["hidden_provider_retries"] is False, "managed hidden retry enabled")
    require(managed["kms_kind"] == "IN_PROCESS_CLOUD_KMS_PROTOCOL_DOUBLE", "managed signer double drift")
    resource = managed["exact_key_version_resource"]
    require(
        type(resource) is str
        and resource.endswith(f"/cryptoKeyVersions/{managed['key_version']}")
        and managed["key_version"] > 0,
        "managed exact key version drift",
    )
    require(managed["algorithm"] == "EC_SIGN_ED25519", "managed algorithm drift")
    require(managed["key_state"] == "ENABLED", "managed key state drift")
    require(managed["protection_level"] == "HSM", "managed protection level drift")
    require(managed["public_key_hex"] == PUBLIC_KEY_HEX, "managed public-key pin drift")

    hosted = profiles["self_hosted"]
    exact_keys(
        hosted,
        {
            "authority_kind",
            "linearizable_reads",
            "nested_transactions",
            "leased_authority_keys",
            "transit_kind",
            "key_version",
            "derived",
            "batch",
            "context",
            "prehashed",
            "hidden_provider_retries",
            "public_key_hex",
            "witness_kind",
            "witness_actor_domain",
        },
        "self-hosted profile",
    )
    require(hosted["authority_kind"] == "IN_MEMORY_ETCD_PROTOCOL_DOUBLE", "etcd double drift")
    require(hosted["linearizable_reads"] is True, "linearizable read disabled")
    require(hosted["nested_transactions"] is False, "nested transactions enabled")
    require(hosted["leased_authority_keys"] is False, "leased authority keys enabled")
    require(hosted["transit_kind"] == "IN_PROCESS_OPENBAO_TRANSIT_PROTOCOL_DOUBLE", "Transit double drift")
    require(type(hosted["key_version"]) is int and hosted["key_version"] > 0, "Transit key version drift")
    require(hosted["derived"] is False, "derived Transit key enabled")
    require(hosted["batch"] is False, "batch Transit request enabled")
    require(hosted["context"] is None, "Transit context must be absent")
    require(hosted["prehashed"] is False, "Transit prehash enabled")
    require(hosted["hidden_provider_retries"] is False, "Transit hidden retry enabled")
    require(hosted["public_key_hex"] == PUBLIC_KEY_HEX, "Transit public-key pin drift")
    require(hosted["witness_kind"] == "IN_MEMORY_EXTERNAL_LINEARIZABLE_CAS_DOUBLE", "witness double drift")
    require(
        hosted["witness_actor_domain"] == "OUTSIDE_ETCD_SNAPSHOT_AND_RESTORE_DOUBLE",
        "witness actor-domain drift",
    )


def validate_contract(contract: Any) -> None:
    require(type(contract) is dict, "contract must be an object")
    require(contract.get("schema") == CONTRACT_SCHEMA, "contract schema drift")
    require(sha256_value(contract) == CONTRACT_SHA256, "contract SHA-256 drift")
    tracks = contract.get("tracks")
    require(type(tracks) is list and len(tracks) == 2, "contract track count drift")
    expected = {MANAGED_TRACK: 16, SELF_HOSTED_TRACK: 18}
    global_ids = {
        invariant["invariant_id"] for invariant in contract.get("global_invariants", [])
    }
    require(global_ids == set(GLOBAL_INVARIANT_IDS), "global invariant catalog drift")
    for track in tracks:
        require(type(track) is dict, "track must be an object")
        track_id = track.get("track_id")
        require(track_id in expected, "unknown contract track")
        cases = track.get("cases")
        track_invariant_ids = {
            invariant["invariant_id"] for invariant in track.get("invariants", [])
        }
        require(track_invariant_ids, "track invariant catalog missing")
        require(type(cases) is list and len(cases) == expected[track_id], "case count drift")
        require(len({case["case_id"] for case in cases}) == len(cases), "duplicate case id")
        for case in cases:
            require(case["permit_allowed"] is False, "contract permits output")
            require(
                set(case["invariant_ids"]) <= global_ids | track_invariant_ids,
                "case invariant reference does not resolve",
            )


def configuration_sha256(configuration: Any) -> str:
    validate_configuration(configuration)
    return sha256_value(configuration)


def build_schedule(contract: Any, configuration: Any) -> list[ScheduleEntry]:
    validate_contract(contract)
    config_sha = configuration_sha256(configuration)
    result: list[ScheduleEntry] = []
    for track in contract["tracks"]:
        track_id = track["track_id"]
        case_ids = [case["case_id"] for case in track["cases"]]
        for repetition in range(1, 31):
            ordered = sorted(
                case_ids,
                key=lambda case_id: _framed_hash_bytes(
                    SCHEDULE_DOMAIN,
                    track_id.encode("utf-8"),
                    repetition.to_bytes(4, "big"),
                    case_id.encode("utf-8"),
                ),
            )
            assignment = {
                "domain": SCHEDULE_DOMAIN,
                "track_id": track_id,
                "repetition_index": repetition,
                "ordered_case_ids": ordered,
                "configuration_sha256": config_sha,
                "contract_sha256": CONTRACT_SHA256,
            }
            assignment_sha = sha256_value(assignment)
            for position, case_id in enumerate(ordered, start=1):
                run_id = _framed_hash_bytes(
                    RUN_DOMAIN,
                    track_id.encode("utf-8"),
                    case_id.encode("utf-8"),
                    repetition.to_bytes(4, "big"),
                    bytes.fromhex(config_sha),
                    bytes.fromhex(assignment_sha),
                )
                namespace_id = _framed_hash_bytes(NAMESPACE_DOMAIN, bytes.fromhex(run_id))
                result.append(
                    ScheduleEntry(
                        track_id=track_id,
                        case_id=case_id,
                        repetition_index=repetition,
                        block_position=position,
                        assignment_sha256=assignment_sha,
                        configuration_sha256=config_sha,
                        run_id=run_id,
                        namespace_id=namespace_id,
                    )
                )
    require(len(result) == 1020, "schedule cardinality drift")
    require(len({(row.track_id, row.case_id, row.repetition_index) for row in result}) == 1020, "duplicate run key")
    require(len({row.run_id for row in result}) == 1020, "duplicate run id")
    require(len({row.namespace_id for row in result}) == 1020, "namespace reuse")
    return result


@dataclass
class CaseOutcome:
    classification: str
    injection_variant: str
    semantic_tokens: list[str]
    request_sha256: str = ZERO_SHA256
    response_sha256: str = ZERO_SHA256
    requested_key_version: int = 0
    validated_key_version: int = 0
    requested_isolation: str = "NOT_APPLICABLE"
    effective_isolation: str = "NOT_APPLICABLE"
    final_state: SimulationState | None = None
    evidence_public_key_sha256: str = PUBLIC_KEY_SHA256


def _managed_authority_commit(
    state: SimulationState,
    exact_key_version: int,
    *,
    attempts: int = 1,
    fault_controller: OneShotFaultController | None = None,
) -> None:
    for attempt in range(1, attempts + 1):
        state.database_attempts += 1
        state.event(
            "SPANNER_SERIALIZABLE_TRANSACTION_ATTEMPT",
            attempt=attempt,
            closure_scope="DATABASE_ONLY",
        )
        if attempt < attempts:
            require(fault_controller is not None, "database abort fault lacks controller")
            fault_controller.trigger(
                state,
                fault_controller.injection_cut,
                _causal_binding(state, f"SPANNER_ATTEMPT_{attempt}_BEFORE_ABORT"),
            )
            state.event("SPANNER_DEFINITE_ABORT", attempt=attempt)
    state.authority = "AUTHORIZED_COMMITTED"
    state.outbox = "SIGN_PENDING"
    state.challenge_consumptions = 1
    state.logical_sink_reservations = 1
    _commit_durable_transition(
        state,
        "KMS",
        "AUTHORITY_OUTBOX_COMMITTED",
        exact_key_version,
        "SPANNER_OUTBOX_COMMITTED",
        outbox="SIGN_PENDING",
    )


def _etcd_authority_commit(state: SimulationState, exact_key_version: int) -> None:
    state.database_attempts += 1
    state.authority = "AUTHORIZED_COMMITTED"
    state.outbox = "SIGN_PENDING"
    state.challenge_consumptions = 1
    state.logical_sink_reservations = 1
    _commit_durable_transition(
        state,
        "TRANSIT",
        "AUTHORITY_OUTBOX_COMMITTED",
        exact_key_version,
        "ETCD_TOP_LEVEL_CAS",
        serializable=False,
        nested=False,
        leased=False,
        response_revision_source="TOP_LEVEL_HEADER",
    )
    state.event("ETCD_OUTBOX_COMMITTED", outbox="SIGN_PENDING")


def _operation_id(state: SimulationState) -> str:
    assignments = [
        event
        for event in state.events
        if event["name"] == "ASSIGNMENT_HASH_SEALED"
    ]
    require(len(assignments) == 1, "prepared attempt lacks a unique assignment")
    operation_id = assignments[0]["details"]["simulation_run_id"]
    require(type(operation_id) is str and len(operation_id) == 64, "operation id drift")
    return operation_id


def _transition_record(state: SimulationState, exact_key_version: int) -> dict[str, Any]:
    return _operation_state_record(
        _operation_id(state),
        exact_key_version,
        authority=state.authority,
        outbox=state.outbox,
        attempt=state.attempt,
        attempt_consumed=state.attempt_consumed,
        receipt=state.receipt,
        challenge_consumptions=state.challenge_consumptions,
        logical_sink_reservations=state.logical_sink_reservations,
        prepared_record_sha256=state.prepared_record_sha256,
        call_binding_sha256=state.call_binding_sha256,
        processed_response_sha256=state.processed_response_sha256,
        validated_response_sha256=state.validated_response_sha256,
        validation_binding_sha256=state.validation_binding_sha256,
        receipt_binding_sha256=state.receipt_binding_sha256,
        terminal=(
            state.terminal_fence != "NONE"
            or state.attempt
            in {"CONSUMED", "AMBIGUOUS_QUARANTINED", "REJECTED_FAIL_CLOSED"}
        ),
    )


def _durable_transition_tip(state: SimulationState) -> tuple[str, int]:
    return (
        state.durable_operation_record_sha256,
        state.durable_operation_revision,
    )


def _commit_exact_record_transition(
    state: SimulationState,
    kind: str,
    phase: str,
    record: dict[str, Any],
    event_name: str,
    **event_details: Any,
) -> None:
    require(kind in {"KMS", "TRANSIT"}, "durable transition kind drift")
    exact_keys(record, set(OPERATION_STATE_RECORD_FIELDS), "operation state record")
    require(
        record["operation_id"] == _operation_id(state),
        "durable transition operation id drift",
    )
    previous_sha256, previous_revision = _durable_transition_tip(state)
    record_sha256 = sha256_value(record)
    managed = kind == "KMS"
    envelope = {
        "phase": phase,
        "store_kind": (
            "SPANNER_SERIALIZABLE_EXACT_KEY_CAS"
            if managed else "ETCD_LINEARIZABLE_TOP_LEVEL_EXACT_KEY_CAS"
        ),
        "operation_id": _operation_id(state),
        "operation_key": _framed_hash(EXACT_KEY_DOMAIN, _operation_id(state)),
        "consistency": "SERIALIZABLE" if managed else "LINEARIZABLE",
        "nested": False,
        "leased": False,
        "compare_record_sha256": previous_sha256,
        "observed_record_sha256": previous_sha256,
        "expected_mod_revision": previous_revision,
        "committed_record_sha256": record_sha256,
        "committed_revision": previous_revision + 1,
        "top_level_revision": previous_revision + 1,
        "mutation_count": 1,
        "cas_result": "APPLIED",
        "response_revision_source": (
            "SERIALIZABLE_COMMIT_MODEL"
            if managed else "TOP_LEVEL_TXN_HEADER"
        ),
    }
    exact_keys(envelope, set(TRANSITION_ENVELOPE_FIELDS), "transition envelope")
    state.event(
        event_name,
        **event_details,
        transition_record=record,
        transition_record_sha256=record_sha256,
        transition_envelope=envelope,
    )
    state.durable_operation_record_sha256 = record_sha256
    state.durable_operation_revision = previous_revision + 1


def _commit_durable_transition(
    state: SimulationState,
    kind: str,
    phase: str,
    exact_key_version: int,
    event_name: str,
    **event_details: Any,
) -> None:
    _commit_exact_record_transition(
        state,
        kind,
        phase,
        _transition_record(state, exact_key_version),
        event_name,
        **event_details,
    )


def _reject_preexecution_transition(
    state: SimulationState,
    event_name: str,
    phase: str,
    exact_key_version: int,
    **event_details: Any,
) -> None:
    """Record a decoded invalid etcd transition without mutating durable state."""

    require(
        state.durable_operation_record_sha256 == ZERO_SHA256
        and state.durable_operation_revision == 0,
        "preexecution rejection followed a durable mutation",
    )
    envelope = {
        "phase": phase,
        "store_kind": "ETCD_LINEARIZABLE_TOP_LEVEL_EXACT_KEY_CAS",
        "operation_id": _operation_id(state),
        "operation_key": _framed_hash(EXACT_KEY_DOMAIN, _operation_id(state)),
        "consistency": "LINEARIZABLE",
        "nested": True,
        "leased": False,
        "compare_record_sha256": ZERO_SHA256,
        "observed_record_sha256": ZERO_SHA256,
        "expected_mod_revision": 0,
        "committed_record_sha256": ZERO_SHA256,
        "committed_revision": 0,
        "top_level_revision": 0,
        "mutation_count": 0,
        "cas_result": "REJECTED_PREEXECUTION",
        "response_revision_source": "NONE_PREEXECUTION_REJECTED",
    }
    exact_keys(envelope, set(TRANSITION_ENVELOPE_FIELDS), "transition envelope")
    require(exact_key_version > 0, "preexecution key version drift")
    state.event(
        event_name,
        **event_details,
        transition_envelope=envelope,
    )


def _causal_binding(state: SimulationState, label: str) -> str:
    return _framed_hash(
        "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/causal-cut",
        _operation_id(state),
        label,
        str(len(state.events) + 1),
    )


def _prepare_attempt(
    state: SimulationState,
    kind: str,
    request_sha: str,
    key_version: int,
) -> None:
    require(state.outbox == "SIGN_PENDING", "attempt requires durable outbox")
    require(state.attempt == "NONE", "attempt marker is single-consumption")
    require(state.prepared_record_sha256 == ZERO_SHA256, "prepared record already exists")
    require(type(key_version) is int and key_version > 0, "prepared key version drift")
    require(
        type(request_sha) is str
        and len(request_sha) == 64
        and all(char in "0123456789abcdef" for char in request_sha),
        "prepared request digest drift",
    )
    record = PreparedAttemptRecord(
        operation_id=_operation_id(state),
        canonical_request_sha256=request_sha,
        exact_key_version=key_version,
        public_key_pin_sha256=PUBLIC_KEY_SHA256,
        message_sha256=MESSAGE_SHA256,
        attempt_sequence=1,
    )
    record_sha = sha256_value(record.as_dict())
    state.attempt = "SIGN_ATTEMPT_PREPARED"
    state.prepared_operation_id = record.operation_id
    state.prepared_request_sha256 = record.canonical_request_sha256
    state.prepared_key_version = record.exact_key_version
    state.prepared_public_key_sha256 = record.public_key_pin_sha256
    state.prepared_message_sha256 = record.message_sha256
    state.prepared_attempt_sequence = record.attempt_sequence
    state.prepared_record_sha256 = record_sha
    _commit_durable_transition(
        state,
        kind,
        "SIGN_ATTEMPT_PREPARED",
        key_version,
        f"{kind}_SIGN_ATTEMPT_PREPARED",
        prepared_record=record.as_dict(),
        prepared_record_sha256=record_sha,
        durable=True,
    )


def _kms_request(configuration: dict[str, Any]) -> dict[str, Any]:
    managed = configuration["profiles"]["managed"]
    return {
        "name": managed["exact_key_version_resource"],
        "data": base64.b64encode(MESSAGE).decode("ascii"),
        "data_crc32c": crc32c(MESSAGE),
    }


def _kms_response(configuration: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    signature = TEST_SIGNATURE
    return {
        "name": request["name"],
        "signature": base64.b64encode(signature).decode("ascii"),
        "signature_crc32c": crc32c(signature),
        "verified_data_crc32c": True,
        "protection_level": configuration["profiles"]["managed"]["protection_level"],
    }


def _validate_kms(
    configuration: dict[str, Any], request: dict[str, Any], response: dict[str, Any]
) -> bool:
    managed = configuration["profiles"]["managed"]
    try:
        raw_message = base64.b64decode(request["data"], validate=True)
        signature = base64.b64decode(response["signature"], validate=True)
    except (KeyError, ValueError):
        return False
    return (
        set(request) == {"name", "data", "data_crc32c"}
        and request["name"] == managed["exact_key_version_resource"]
        and raw_message == MESSAGE
        and len(raw_message) == 137
        and request["data_crc32c"] == crc32c(raw_message)
        and response.get("verified_data_crc32c") is True
        and response.get("name") == request["name"]
        and response.get("signature_crc32c") == crc32c(signature)
        and response.get("protection_level") == managed["protection_level"]
        and ed25519_verify(signature, raw_message, bytes.fromhex(managed["public_key_hex"]))
    )


def _transit_request(configuration: dict[str, Any]) -> dict[str, Any]:
    hosted = configuration["profiles"]["self_hosted"]
    return {
        "input": base64.b64encode(MESSAGE).decode("ascii"),
        "key_version": hosted["key_version"],
        "prehashed": False,
    }


def _transit_response(configuration: dict[str, Any]) -> dict[str, Any]:
    version = configuration["profiles"]["self_hosted"]["key_version"]
    signature = base64.b64encode(TEST_SIGNATURE).decode("ascii")
    return {"signature": f"vault:v{version}:{signature}"}


def _validate_transit(
    configuration: dict[str, Any], request: dict[str, Any], response: dict[str, Any]
) -> bool:
    hosted = configuration["profiles"]["self_hosted"]
    try:
        raw = base64.b64decode(request["input"], validate=True)
        prefix, version_text, encoded_signature = response["signature"].split(":", 2)
        signature = base64.b64decode(encoded_signature, validate=True)
    except (KeyError, ValueError):
        return False
    return (
        set(request) == {"input", "key_version", "prehashed"}
        and raw == MESSAGE
        and len(raw) == 137
        and request["key_version"] == hosted["key_version"] > 0
        and request["prehashed"] is False
        and prefix == "vault"
        and version_text == f"v{request['key_version']}"
        and ed25519_verify(signature, raw, bytes.fromhex(hosted["public_key_hex"]))
    )


def _double_call(
    state: SimulationState,
    kind: str,
    request: dict[str, Any],
    response: dict[str, Any],
    *,
    drop_response: bool = False,
    fault_controller: OneShotFaultController | None = None,
    fault_cut: str | None = None,
    correlation: S12ExecutionCorrelation | None = None,
) -> dict[str, Any] | None:
    require(state.attempt == "SIGN_ATTEMPT_PREPARED", "double call lacks prepared marker")
    request_sha = sha256_value(request)
    response_sha = sha256_value(response)
    require(request_sha == state.prepared_request_sha256, "double request does not match prepared record")
    require(state.prepared_operation_id == _operation_id(state), "prepared operation binding drift")
    require(state.prepared_key_version > 0, "prepared key version missing")
    require(state.prepared_public_key_sha256 == PUBLIC_KEY_SHA256, "prepared public-key pin drift")
    require(state.prepared_message_sha256 == MESSAGE_SHA256, "prepared message binding drift")
    require(state.prepared_attempt_sequence == 1, "prepared attempt sequence drift")
    require(state.prepared_record_sha256 != ZERO_SHA256, "prepared record hash missing")
    reconstructed = PreparedAttemptRecord(
        operation_id=state.prepared_operation_id,
        canonical_request_sha256=state.prepared_request_sha256,
        exact_key_version=state.prepared_key_version,
        public_key_pin_sha256=state.prepared_public_key_sha256,
        message_sha256=state.prepared_message_sha256,
        attempt_sequence=state.prepared_attempt_sequence,
    )
    require(
        sha256_value(reconstructed.as_dict()) == state.prepared_record_sha256,
        "prepared record hash does not match durable fields",
    )
    if kind == "KMS":
        require(
            type(request.get("name")) is str
            and request["name"].endswith(
                f"/cryptoKeyVersions/{state.prepared_key_version}"
            ),
            "KMS request version does not match prepared record",
        )
    elif kind == "TRANSIT":
        require(
            request.get("key_version") == state.prepared_key_version,
            "Transit request version does not match prepared record",
        )
    else:
        raise HarnessError("unsupported double kind")
    require(state.attempt_consumed is False, "prepared attempt was already consumed")
    require(state.simulated_application_calls == 0, "second simulated call rejected before processing")
    execution_request_id = None if correlation is None else correlation.request_id
    executing_node = None if correlation is None else correlation.executing_node
    execution_cluster_id = None if correlation is None else correlation.cluster_id
    audit_record_sha256 = None if correlation is None else correlation.audit_record_sha256
    wire_attempt_sha256 = None if correlation is None else correlation.wire_attempt_sha256
    call_binding = _framed_hash(
        "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/double-call",
        state.prepared_record_sha256,
        request_sha,
        execution_request_id or "NOT_APPLICABLE",
        executing_node or "NOT_APPLICABLE",
        execution_cluster_id or "NOT_APPLICABLE",
        audit_record_sha256 or "NOT_APPLICABLE",
        wire_attempt_sha256 or "NOT_APPLICABLE",
    )
    state.attempt_consumed = True
    state.call_binding_sha256 = call_binding
    state.simulated_application_calls += 1
    _commit_durable_transition(
        state,
        kind,
        "SIGN_ATTEMPT_CALL_CONSUMED",
        state.prepared_key_version,
        f"{kind}_SIGN_ATTEMPT_CALL_CONSUMED",
    )
    state.event(
        f"{kind}_DOUBLE_CALL",
        operation_id=state.prepared_operation_id,
        prepared_record_sha256=state.prepared_record_sha256,
        request_sha256=request_sha,
        key_version=state.prepared_key_version,
        public_key_sha256=state.prepared_public_key_sha256,
        message_sha256=state.prepared_message_sha256,
        attempt_sequence=state.prepared_attempt_sequence,
        call_binding_sha256=call_binding,
        hidden_retries=False,
        evidence_class=EVIDENCE_CLASS,
        execution_request_id=execution_request_id,
        executing_node=executing_node,
        execution_cluster_id=execution_cluster_id,
        audit_record_sha256=audit_record_sha256,
        wire_attempt_sha256=wire_attempt_sha256,
    )
    state.processed_response_sha256 = response_sha
    state.simulated_processing_events += 1
    state.event(
        f"{kind}_DOUBLE_PROCESSING_COMPLETED",
        call_binding_sha256=call_binding,
        response_sha256=response_sha,
    )
    if drop_response:
        require(fault_controller is not None and fault_cut is not None, "response drop lacks fault controller")
        fault_controller.trigger(state, fault_cut, call_binding)
        state.event(
            f"{kind}_DOUBLE_RESPONSE_DROPPED",
            call_binding_sha256=call_binding,
            response_sha256=response_sha,
        )
        return None
    state.event(
        f"{kind}_DOUBLE_RESPONSE_OBSERVED",
        call_binding_sha256=call_binding,
        response_sha256=response_sha,
    )
    return response


def _mark_response_validated(
    state: SimulationState,
    kind: str,
    configuration: dict[str, Any],
    request: dict[str, Any],
    response: dict[str, Any],
    *,
    correlation: S12ExecutionCorrelation | None = None,
) -> None:
    require(state.attempt == "SIGN_ATTEMPT_PREPARED", "validation lacks prepared state")
    require(state.attempt_consumed is True, "validation preceded simulated call")
    require(state.simulated_application_calls == 1, "validation call cardinality drift")
    require(state.validated_response_sha256 == ZERO_SHA256, "response validated more than once")
    require(sha256_value(request) == state.prepared_request_sha256, "validation request differs from prepared request")
    if kind == "KMS":
        require(_validate_kms(configuration, request, response), "KMS response failed full validation")
    elif kind == "TRANSIT":
        require(_validate_transit(configuration, request, response), "Transit response failed full validation")
    else:
        raise HarnessError("unsupported validation kind")
    response_sha = sha256_value(response)
    require(
        response_sha == state.processed_response_sha256,
        "validated response differs from processed response",
    )
    execution_request_id = None if correlation is None else correlation.request_id
    executing_node = None if correlation is None else correlation.executing_node
    execution_cluster_id = None if correlation is None else correlation.cluster_id
    audit_record_sha256 = None if correlation is None else correlation.audit_record_sha256
    wire_attempt_sha256 = None if correlation is None else correlation.wire_attempt_sha256
    binding = _framed_hash(
        "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/response-validation",
        state.call_binding_sha256,
        response_sha,
        state.prepared_request_sha256,
        str(state.prepared_key_version),
        state.prepared_public_key_sha256,
        state.prepared_message_sha256,
        execution_request_id or "NOT_APPLICABLE",
        executing_node or "NOT_APPLICABLE",
        execution_cluster_id or "NOT_APPLICABLE",
        audit_record_sha256 or "NOT_APPLICABLE",
        wire_attempt_sha256 or "NOT_APPLICABLE",
    )
    state.validated_response_sha256 = response_sha
    state.validation_binding_sha256 = binding
    state.event(
        f"{kind}_RESPONSE_FULLY_VALIDATED",
        operation_id=state.prepared_operation_id,
        request_sha256=state.prepared_request_sha256,
        response_sha256=response_sha,
        key_version=state.prepared_key_version,
        public_key_sha256=state.prepared_public_key_sha256,
        message_sha256=state.prepared_message_sha256,
        message_bytes=len(MESSAGE),
        call_binding_sha256=state.call_binding_sha256,
        validation_binding_sha256=binding,
        execution_request_id=execution_request_id,
        executing_node=executing_node,
        execution_cluster_id=execution_cluster_id,
        audit_record_sha256=audit_record_sha256,
        wire_attempt_sha256=wire_attempt_sha256,
    )


def _commit_receipt(
    state: SimulationState,
    kind: str,
    *,
    correlation: S12ExecutionCorrelation | None = None,
) -> None:
    require(state.attempt == "SIGN_ATTEMPT_PREPARED", "receipt commit lacks prepared state")
    require(state.attempt_consumed is True, "receipt commit preceded simulated call")
    require(state.simulated_application_calls == 1, "receipt commit call cardinality drift")
    require(state.validated_response_sha256 != ZERO_SHA256, "receipt commit preceded full validation")
    require(state.validation_binding_sha256 != ZERO_SHA256, "receipt validation binding missing")
    require(state.receipt_binding_sha256 == ZERO_SHA256, "receipt committed more than once")
    execution_request_id = None if correlation is None else correlation.request_id
    executing_node = None if correlation is None else correlation.executing_node
    execution_cluster_id = None if correlation is None else correlation.cluster_id
    audit_record_sha256 = None if correlation is None else correlation.audit_record_sha256
    wire_attempt_sha256 = None if correlation is None else correlation.wire_attempt_sha256
    expected_call_binding = _framed_hash(
        "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/double-call",
        state.prepared_record_sha256,
        state.prepared_request_sha256,
        execution_request_id or "NOT_APPLICABLE",
        executing_node or "NOT_APPLICABLE",
        execution_cluster_id or "NOT_APPLICABLE",
        audit_record_sha256 or "NOT_APPLICABLE",
        wire_attempt_sha256 or "NOT_APPLICABLE",
    )
    expected_validation_binding = _framed_hash(
        "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/response-validation",
        expected_call_binding,
        state.validated_response_sha256,
        state.prepared_request_sha256,
        str(state.prepared_key_version),
        state.prepared_public_key_sha256,
        state.prepared_message_sha256,
        execution_request_id or "NOT_APPLICABLE",
        executing_node or "NOT_APPLICABLE",
        execution_cluster_id or "NOT_APPLICABLE",
        audit_record_sha256 or "NOT_APPLICABLE",
        wire_attempt_sha256 or "NOT_APPLICABLE",
    )
    require(
        state.call_binding_sha256 == expected_call_binding
        and state.validation_binding_sha256 == expected_validation_binding
        and state.processed_response_sha256 == state.validated_response_sha256,
        "receipt causal binding reconstruction drift",
    )
    receipt_binding = _framed_hash(
        "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/durable-receipt",
        state.prepared_record_sha256,
        state.call_binding_sha256,
        state.validation_binding_sha256,
        state.validated_response_sha256,
        execution_request_id or "NOT_APPLICABLE",
        executing_node or "NOT_APPLICABLE",
        execution_cluster_id or "NOT_APPLICABLE",
        audit_record_sha256 or "NOT_APPLICABLE",
        wire_attempt_sha256 or "NOT_APPLICABLE",
    )
    state.attempt = "CONSUMED"
    state.receipt = "SIGNATURE_RECEIPT_COMMITTED"
    state.receipt_binding_sha256 = receipt_binding
    _commit_durable_transition(
        state,
        kind,
        "SIGNATURE_RECEIPT_COMMITTED",
        state.prepared_key_version,
        f"{kind}_SIGNATURE_RECEIPT_COMMITTED",
        operation_id=state.prepared_operation_id,
        prepared_record_sha256=state.prepared_record_sha256,
        request_sha256=state.prepared_request_sha256,
        response_sha256=state.validated_response_sha256,
        key_version=state.prepared_key_version,
        public_key_sha256=state.prepared_public_key_sha256,
        message_sha256=state.prepared_message_sha256,
        call_binding_sha256=state.call_binding_sha256,
        validation_binding_sha256=state.validation_binding_sha256,
        receipt_binding_sha256=receipt_binding,
        execution_request_id=execution_request_id,
        executing_node=executing_node,
        execution_cluster_id=execution_cluster_id,
        audit_record_sha256=audit_record_sha256,
        wire_attempt_sha256=wire_attempt_sha256,
    )


def _quarantine(state: SimulationState, kind: str) -> None:
    require(state.attempt == "SIGN_ATTEMPT_PREPARED", "quarantine lacks prepared state")
    require(state.attempt_consumed is True, "quarantine preceded simulated call")
    require(state.simulated_application_calls == 1, "quarantine call cardinality drift")
    require(state.processed_response_sha256 != ZERO_SHA256, "quarantine lacks processed response")
    require(
        state.call_binding_sha256
        == _framed_hash(
            "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/double-call",
            state.prepared_record_sha256,
            state.prepared_request_sha256,
            "NOT_APPLICABLE",
            "NOT_APPLICABLE",
            "NOT_APPLICABLE",
            "NOT_APPLICABLE",
            "NOT_APPLICABLE",
        ),
        "quarantine call binding drift",
    )
    state.attempt = "AMBIGUOUS_QUARANTINED"
    state.receipt = "NONE"
    _commit_durable_transition(
        state,
        kind,
        "AMBIGUOUS_QUARANTINED",
        state.prepared_key_version,
        f"{kind}_AMBIGUOUS_QUARANTINED",
        operation_id=state.prepared_operation_id,
        prepared_record_sha256=state.prepared_record_sha256,
        call_binding_sha256=state.call_binding_sha256,
        validation_binding_sha256=state.validation_binding_sha256,
    )


def _restart(state: SimulationState) -> SimulationState:
    calls_before = state.simulated_application_calls
    durable_image = canonical_bytes(state.snapshot())
    durable_snapshot = json.loads(durable_image.decode("utf-8"))
    state.event(
        "DURABLE_IMAGE_SERIALIZED",
        durable_image=durable_snapshot,
        image_sha256=sha256_bytes(durable_image),
    )
    state.event("EPHEMERAL_WORKER_DESTROYED")
    require(
        state.attempt in {"AMBIGUOUS_QUARANTINED", "CONSUMED", "NONE"},
        "restart encountered unresolved prepared state",
    )
    restored_image = durable_snapshot
    require(canonical_bytes(restored_image) == durable_image, "durable image reconstruction drift")
    new_state = SimulationState(**restored_image)
    new_state.events = list(state.events)
    new_state.restarts += 1
    new_state.event(
        "WORKER_RESTARTED",
        calls_before_restart=calls_before,
        durable_attempt_state=new_state.attempt,
    )
    new_state.event(
        "NEW_WORKER_CONSTRUCTED_FROM_DURABLE_IMAGE",
        prior_worker_ephemeral_state_reused=False,
        state_object_reused=False,
    )
    new_state.event(
        "RESTART_NO_RESIGN_CONFIRMED",
        calls_after_restart=new_state.simulated_application_calls,
    )
    return new_state


def _managed_success(
    state: SimulationState,
    configuration: dict[str, Any],
    *,
    database_attempts: int = 1,
    fault_controller: OneShotFaultController | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _managed_authority_commit(
        state,
        configuration["profiles"]["managed"]["key_version"],
        attempts=database_attempts,
        fault_controller=fault_controller,
    )
    request = _kms_request(configuration)
    _prepare_attempt(
        state,
        "KMS",
        sha256_value(request),
        configuration["profiles"]["managed"]["key_version"],
    )
    response = _kms_response(configuration, request)
    observed = _double_call(state, "KMS", request, response)
    require(observed is not None and _validate_kms(configuration, request, observed), "valid KMS double response rejected")
    _mark_response_validated(state, "KMS", configuration, request, observed)
    _commit_receipt(state, "KMS")
    return request, response


def _self_hosted_success(
    state: SimulationState,
    configuration: dict[str, Any],
    *,
    correlation: S12ExecutionCorrelation | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _etcd_authority_commit(
        state, configuration["profiles"]["self_hosted"]["key_version"]
    )
    request = _transit_request(configuration)
    _prepare_attempt(
        state,
        "TRANSIT",
        sha256_value(request),
        configuration["profiles"]["self_hosted"]["key_version"],
    )
    response = _transit_response(configuration)
    observed = _double_call(
        state,
        "TRANSIT",
        request,
        response,
        correlation=correlation,
    )
    require(observed is not None and _validate_transit(configuration, request, observed), "valid Transit double response rejected")
    _mark_response_validated(
        state,
        "TRANSIT",
        configuration,
        request,
        observed,
        correlation=correlation,
    )
    _commit_receipt(state, "TRANSIT", correlation=correlation)
    return request, response


def _fail_response_validation(state: SimulationState, kind: str, reason: str) -> None:
    require(state.attempt == "SIGN_ATTEMPT_PREPARED", "response rejection lacks prepared attempt")
    require(state.attempt_consumed is True, "response rejection preceded simulated call")
    require(state.validated_response_sha256 == ZERO_SHA256, "validated response cannot be rejected")
    state.attempt = "REJECTED_FAIL_CLOSED"
    state.receipt = "NONE"
    _commit_durable_transition(
        state,
        kind,
        "RESPONSE_REJECTED_FAIL_CLOSED",
        state.prepared_key_version,
        f"{kind}_RESPONSE_REJECTED",
        reason=reason,
        operation_id=state.prepared_operation_id,
        prepared_record_sha256=state.prepared_record_sha256,
        call_binding_sha256=state.call_binding_sha256,
    )


def _managed_case(
    case_id: str,
    repetition: int,
    state: SimulationState,
    configuration: dict[str, Any],
    fault_controller: OneShotFaultController,
) -> CaseOutcome:
    managed = configuration["profiles"]["managed"]
    key_version = managed["key_version"]
    isolation = managed["effective_isolation"]

    if case_id == "M00":
        request, response = _managed_success(state, configuration)
        return CaseOutcome(
            "CONFORMING_OBSERVED", "NONE",
            ["SERIALIZABLE_OUTBOX", "PREPARED_BEFORE_DOUBLE_CALL", "FULL_KMS_VALIDATION", "DURABLE_RECEIPT"],
            sha256_value(request), sha256_value(response), key_version, key_version,
            isolation, isolation,
        )
    if case_id == "M01":
        request, response = _managed_success(
            state,
            configuration,
            database_attempts=2,
            fault_controller=fault_controller,
        )
        return CaseOutcome(
            "RECOVERED_BY_DATABASE_ONLY_RETRY", "ABORT_FIRST_TRANSACTION_ATTEMPT_BEFORE_COMMIT",
            ["DATABASE_ONLY_RETRY", "STABLE_OPERATION_ID", "NO_EXTERNAL_SIDE_EFFECT_REPLAY", "FULL_KMS_VALIDATION"],
            sha256_value(request), sha256_value(response), key_version, key_version,
            isolation, isolation,
        )
    if case_id == "M02":
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            _causal_binding(state, "RETRYABLE_CLOSURE_SIDE_EFFECT_SENTINEL"),
        )
        state.event("SPANNER_CLOSURE_SIDE_EFFECT_SENTINEL_REJECTED", attempted="KMS")
        state.authority = "REJECTED_FAIL_CLOSED"
        return CaseOutcome(
            "FAIL_CLOSED_REJECTED", "ATTEMPT_EXTERNAL_SIDE_EFFECT_FROM_RETRYABLE_CLOSURE",
            ["STATIC_CALL_GRAPH_REJECTED", "RUNTIME_SIDE_EFFECT_SENTINEL", "ZERO_DOUBLE_CALLS"],
            requested_isolation=isolation, effective_isolation=isolation,
        )
    if case_id == "M03":
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            _causal_binding(state, "REQUESTED_ISOLATION_PROFILE"),
        )
        state.event("SPANNER_ISOLATION_PROFILE_REJECTED", requested="REPEATABLE_READ", required="SERIALIZABLE")
        state.authority = "REJECTED_FAIL_CLOSED"
        return CaseOutcome(
            "FAIL_CLOSED_REJECTED", "REQUEST_REPEATABLE_READ_ISOLATION",
            ["REQUESTED_ISOLATION_REJECTED", "EFFECTIVE_ISOLATION_NOT_STARTED", "ZERO_DOUBLE_CALLS"],
            requested_isolation="REPEATABLE_READ", effective_isolation="NOT_STARTED",
        )
    if case_id == "M04":
        store = ExactKeyCASDouble.for_run(_operation_id(state))
        operation_record = store.operation_record(_operation_id(state), key_version)
        state.database_attempts = 1
        if repetition % 2:
            store.commit_now(operation_record)
            state.authority = "AUTHORIZED_COMMITTED"
            state.outbox = "SIGN_PENDING"
            state.challenge_consumptions = 1
            state.logical_sink_reservations = 1
            _commit_exact_record_transition(
                state,
                "KMS",
                "AUTHORITY_OUTBOX_COMMITTED",
                operation_record,
                "SPANNER_SERVER_COMMIT_APPLIED",
                operation_key=store.operation_key,
                record_sha256=sha256_value(operation_record),
                revision=store.revision,
            )
            fault_controller.trigger(
                state,
                fault_controller.injection_cut,
                sha256_value(operation_record),
            )
            state.event(
                "SPANNER_COMMIT_RESPONSE_LOST",
                operation_key=store.operation_key,
                server_commit=True,
                record_sha256=sha256_value(operation_record),
            )
            store.exact_read(
                state,
                "SPANNER_EXACT_STRONG_LOOKUP",
                consistency="STRONG",
                expected_kind="EXACT_OPERATION_RECORD",
            )
            variant = "DROP_COMMIT_RESPONSE_AFTER_SERVER_COMMIT"
            tokens = ["UNKNOWN_NOT_BLINDLY_REISSUED", "EXACT_RECORD_STRONG_LOOKUP", "OUTBOX_RECOVERED"]
        else:
            store.stage_delayed_commit(operation_record)
            state.event(
                "SPANNER_COMMIT_ADMITTED_OUTCOME_UNRESOLVED",
                operation_key=store.operation_key,
                delayed_record_sha256=sha256_value(operation_record),
            )
            fault_controller.trigger(
                state,
                fault_controller.injection_cut,
                sha256_value(operation_record),
            )
            state.event(
                "SPANNER_COMMIT_RESPONSE_LOST",
                operation_key=store.operation_key,
                server_commit="UNRESOLVED",
                record_sha256=ZERO_SHA256,
            )
            require(
                store.exact_read(
                    state,
                    "SPANNER_BARE_ABSENT_STRONG_READ",
                    consistency="STRONG",
                )
                is None,
                "managed bare absent read drift",
            )
            store.cas_absent_to_terminal_fence(
                state,
                "SPANNER_ABSENT_TO_TERMINAL_FENCE_TRANSACTION",
                kind="KMS",
                consistency="SERIALIZABLE",
                operation_id=_operation_id(state),
                exact_key_version=key_version,
            )
            store.exact_read(
                state,
                "SPANNER_CONFIRMING_STRONG_READ",
                consistency="STRONG",
                expected_kind="TERMINAL_FENCE",
            )
            store.release_delayed_commit(state, "SPANNER_DELAYED_COMMIT_FENCE_CONFLICT")
            state.terminal_fence = "DURABLY_FENCED_ABSENCE"
            state.authority = "FENCED_ABSENT"
            variant = "DROP_COMMIT_RESPONSE_WHILE_COMMIT_OUTCOME_IS_UNRESOLVED"
            tokens = ["UNKNOWN_NOT_BLINDLY_REISSUED", "BARE_ABSENCE_NONTERMINAL", "SAME_OPERATION_TERMINAL_FENCE", "CONFIRMING_STRONG_READ"]
        return CaseOutcome(
            "RECOVERED_BY_STRONG_LOOKUP", variant, tokens,
            requested_isolation=isolation, effective_isolation=isolation,
        )
    if case_id in {"M05", "M06"}:
        _managed_authority_commit(state, key_version)
        base_request = _kms_request(configuration)
        if case_id == "M05":
            request = {
                "name": base_request["name"],
                "digest": {
                    "sha256": base64.b64encode(
                        bytes.fromhex(MESSAGE_SHA256)
                    ).decode("ascii")
                },
            }
            reason = "DIGEST_UNION_ARM_FORBIDDEN"
        else:
            mutated_message = MESSAGE[:-1] + bytes([MESSAGE[-1] ^ 1])
            request = {
                "name": base_request["name"],
                "data": base64.b64encode(mutated_message).decode("ascii"),
                "data_crc32c": crc32c(mutated_message),
            }
            reason = "MESSAGE_FRAME_MISMATCH"
        request_sha256 = sha256_value(request)
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            request_sha256,
        )
        state.attempt = "REJECTED_FAIL_CLOSED"
        _commit_durable_transition(
            state,
            "KMS",
            "PRE_ATTEMPT_REJECTED_FAIL_CLOSED",
            key_version,
            "KMS_REQUEST_REJECTED_BEFORE_ATTEMPT",
            reason=reason,
        )
        variant = (
            "PLACE_AUTHORITY_DECISION_HASH_IN_DIGEST_FIELD"
            if case_id == "M05" else "MUTATE_ONE_FRAME_BYTE_OR_LENGTH"
        )
        tokens = (
            ["DATA_ARM_REQUIRED", "DIGEST_ARM_ABSENT", "ZERO_DOUBLE_CALLS"]
            if case_id == "M05"
            else ["EXACT_137_BYTE_FRAME_REQUIRED", "MESSAGE_SHA256_MISMATCH_REJECTED", "ZERO_DOUBLE_CALLS"]
        )
        return CaseOutcome(
            "FAIL_CLOSED_REJECTED", variant, tokens,
            request_sha256=request_sha256,
            requested_key_version=key_version,
            requested_isolation=isolation, effective_isolation=isolation,
        )
    if case_id == "M07":
        _managed_authority_commit(state, key_version)
        request = _kms_request(configuration)
        if repetition % 2:
            fault_controller.trigger(
                state,
                fault_controller.injection_cut,
                sha256_value(request),
            )
            request["data_crc32c"] = crc32c(request["data"].encode("ascii"))
            _prepare_attempt(state, "KMS", sha256_value(request), key_version)
            variant = "COMPUTE_DATA_CRC32C_OVER_BASE64_TEXT"
            observed = _double_call(state, "KMS", request, {"provider_error": "CRC32C_MISMATCH"})
            require(observed is not None, "explicit provider-double error lost")
            _fail_response_validation(state, "KMS", "RAW_DATA_CRC32C_MISMATCH")
            response_hash = sha256_value(observed)
            tokens = ["CRC32C_OVER_RAW_BYTES", "BASE64_TEXT_CRC_REJECTED", "EXPLICIT_DOUBLE_ERROR"]
        else:
            _prepare_attempt(state, "KMS", sha256_value(request), key_version)
            response = _kms_response(configuration, request)
            fault_controller.trigger(
                state,
                fault_controller.injection_cut,
                sha256_value(response),
            )
            response["verified_data_crc32c"] = False
            variant = "RETURN_VERIFIED_DATA_CRC32C_FALSE"
            observed = _double_call(state, "KMS", request, response)
            require(observed is not None, "mutated response lost")
            _fail_response_validation(state, "KMS", "VERIFIED_DATA_CRC32C_FALSE")
            response_hash = sha256_value(response)
            tokens = ["CRC32C_OVER_RAW_BYTES", "VERIFIED_DATA_CRC32C_REQUIRED", "FALSE_VERIFICATION_REJECTED"]
        return CaseOutcome(
            "FAIL_CLOSED_REJECTED", variant, tokens,
            sha256_value(request), response_hash, key_version, 0, isolation, isolation,
        )
    if case_id == "M08":
        variants = [
            "OMIT_CRYPTOKEYVERSION_SEGMENT",
            "SET_CRYPTOKEYVERSION_SEGMENT_TO_ZERO",
            "USE_PARENT_CRYPTOKEY_RESOURCE",
            "USE_NONCANONICAL_LEADING_ZERO_VERSION",
            "RETURN_DIFFERENT_CRYPTOKEYVERSION_NAME",
        ]
        variant = variants[(repetition - 1) % len(variants)]
        _managed_authority_commit(state, key_version)
        request = _kms_request(configuration)
        requested_version = key_version
        if variant != "RETURN_DIFFERENT_CRYPTOKEYVERSION_NAME":
            fault_controller.trigger(
                state,
                fault_controller.injection_cut,
                sha256_value(request),
            )
            if variant == "OMIT_CRYPTOKEYVERSION_SEGMENT":
                request["name"] = request["name"].replace(
                    "/cryptoKeyVersions/", "/", 1
                )
                requested_version = 0
            elif variant == "SET_CRYPTOKEYVERSION_SEGMENT_TO_ZERO":
                request["name"] = request["name"].rsplit("/", 1)[0] + "/0"
                requested_version = 0
            elif variant == "USE_PARENT_CRYPTOKEY_RESOURCE":
                request["name"] = request["name"].split("/cryptoKeyVersions/", 1)[0]
                requested_version = 0
            else:
                request["name"] = request["name"].rsplit("/", 1)[0] + f"/0{key_version}"
            state.attempt = "REJECTED_FAIL_CLOSED"
            _commit_durable_transition(
                state,
                "KMS",
                "PRE_ATTEMPT_REJECTED_FAIL_CLOSED",
                key_version,
                "KMS_RESOURCE_REJECTED_BEFORE_ATTEMPT",
                variant=variant,
            )
            response_hash = ZERO_SHA256
            tokens = ["EXACT_VERSION_RESOURCE_REQUIRED", "INVALID_RESOURCE_REJECTED_PRECALL", "ZERO_DOUBLE_CALLS"]
        else:
            _prepare_attempt(state, "KMS", sha256_value(request), key_version)
            response = _kms_response(configuration, request)
            fault_controller.trigger(
                state,
                fault_controller.injection_cut,
                sha256_value(response),
            )
            response["name"] = response["name"].rsplit("/", 1)[0] + f"/{key_version + 1}"
            observed = _double_call(state, "KMS", request, response)
            require(observed is not None, "name-mismatch response lost")
            _fail_response_validation(state, "KMS", "RESPONSE_NAME_MISMATCH")
            response_hash = sha256_value(response)
            tokens = ["EXACT_VERSION_RESOURCE_REQUIRED", "RESPONSE_NAME_BYTE_EQUALITY", "MISMATCHED_RESPONSE_NAME_REJECTED"]
        return CaseOutcome(
            "FAIL_CLOSED_REJECTED", variant, tokens,
            sha256_value(request), response_hash, requested_version, 0, isolation, isolation,
        )
    if case_id in {"M09", "M10", "M11"}:
        _managed_authority_commit(state, key_version)
        request = _kms_request(configuration)
        _prepare_attempt(state, "KMS", sha256_value(request), key_version)
        response = _kms_response(configuration, request)
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            sha256_value(response),
        )
        if case_id == "M09":
            response["signature_crc32c"] ^= 1
            reason = "SIGNATURE_CRC32C_MISMATCH"
            variant = "CORRUPT_SIGNATURE_OR_SIGNATURE_CRC32C"
            tokens = ["LOCAL_SIGNATURE_CRC32C", "CORRUPT_SIGNATURE_REJECTED"]
        elif case_id == "M10":
            response["protection_level"] = "HSM_SINGLE_TENANT"
            reason = "PROTECTION_LEVEL_MISMATCH"
            variant = "RETURN_DIFFERENT_PROTECTION_LEVEL_FROM_PINNED_EXPECTATION"
            tokens = ["EXACT_PROTECTION_ENUM", "HSM_ENUM_DISTINCTION"]
        else:
            signature = bytearray(base64.b64decode(response["signature"]))
            signature[0] ^= 1
            response["signature"] = base64.b64encode(signature).decode("ascii")
            response["signature_crc32c"] = crc32c(bytes(signature))
            reason = "PINNED_KEY_VERIFICATION_FAILED"
            variant = "RETURN_SIGNATURE_THAT_FAILS_PINNED_KEY_VERIFICATION"
            tokens = ["PINNED_PUBLIC_KEY", "OFFLINE_ED25519_VERIFY", "INVALID_SIGNATURE_REJECTED"]
        observed = _double_call(state, "KMS", request, response)
        require(observed is not None and not _validate_kms(configuration, request, observed), "negative KMS response unexpectedly valid")
        _fail_response_validation(state, "KMS", reason)
        return CaseOutcome(
            "FAIL_CLOSED_REJECTED", variant, tokens,
            sha256_value(request), sha256_value(response), key_version, 0, isolation, isolation,
        )
    if case_id == "M12":
        _managed_authority_commit(state, key_version)
        request = _kms_request(configuration)
        _prepare_attempt(state, "KMS", sha256_value(request), key_version)
        response = _kms_response(configuration, request)
        require(
            _double_call(
                state,
                "KMS",
                request,
                response,
                drop_response=True,
                fault_controller=fault_controller,
                fault_cut=fault_controller.injection_cut,
            )
            is None,
            "drop fault failed",
        )
        _quarantine(state, "KMS")
        state = _restart(state)
        return CaseOutcome(
            "AMBIGUOUS_QUARANTINED", "DROP_KMS_RESPONSE_AFTER_SERVICE_PROCESSING_THEN_RESTART_WORKER",
            ["DURABLE_PREPARED_MARKER", "LOST_RESPONSE_NOT_NO_SIGN_PROOF", "TERMINAL_QUARANTINE", "RESTART_NO_RESIGN"],
            sha256_value(request), ZERO_SHA256, key_version, 0, isolation, isolation,
            final_state=state,
        )
    if case_id == "M13":
        _managed_authority_commit(state, key_version)
        request = _kms_request(configuration)
        _prepare_attempt(state, "KMS", sha256_value(request), key_version)
        response = _kms_response(configuration, request)
        observed = _double_call(state, "KMS", request, response)
        require(observed is not None and _validate_kms(configuration, request, observed), "valid response missing")
        _mark_response_validated(state, "KMS", configuration, request, observed)
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            state.validation_binding_sha256,
        )
        state.event("SPANNER_RECEIPT_PERSIST_OUTCOME_UNKNOWN")
        if repetition % 2:
            _commit_receipt(state, "KMS")
            state.event(
                "SPANNER_STRONG_EXACT_RECEIPT_LOOKUP",
                result="EXACT_RECEIPT",
                operation_id=state.prepared_operation_id,
                receipt_binding_sha256=state.receipt_binding_sha256,
            )
            classification = "RECOVERED_BY_STRONG_LOOKUP"
            tokens = ["IN_MEMORY_SIGNATURE_NOT_DURABLE", "EXACT_RECEIPT_RECOVERED", "RESTART_NO_RESIGN"]
        else:
            state.event(
                "SPANNER_STRONG_EXACT_RECEIPT_LOOKUP",
                result="ABSENT",
                operation_id=state.prepared_operation_id,
                receipt_binding_sha256=ZERO_SHA256,
            )
            _quarantine(state, "KMS")
            classification = "AMBIGUOUS_QUARANTINED"
            tokens = ["IN_MEMORY_SIGNATURE_NOT_DURABLE", "ABSENT_RECEIPT_QUARANTINED", "RESTART_NO_RESIGN"]
        state = _restart(state)
        return CaseOutcome(
            classification, "FAIL_RECEIPT_PERSIST_AFTER_SIGNATURE_VALIDATION_THEN_RESTART_WORKER", tokens,
            sha256_value(request), sha256_value(response), key_version,
            key_version,
            isolation, isolation,
            final_state=state,
        )
    if case_id == "M14":
        _managed_authority_commit(state, key_version)
        request = _kms_request(configuration)
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            state.prepared_operation_id if state.prepared_operation_id != ZERO_SHA256 else _operation_id(state),
        )
        state.event("TWO_WORKERS_RELEASED", workers=2)
        _prepare_attempt(state, "KMS", sha256_value(request), key_version)
        state.event("LOSING_WORKER_ATTEMPT_CAS_CONFLICT", simulated_calls=0)
        response = _kms_response(configuration, request)
        observed = _double_call(state, "KMS", request, response)
        require(observed is not None and _validate_kms(configuration, request, observed), "winner response invalid")
        _mark_response_validated(state, "KMS", configuration, request, observed)
        _commit_receipt(state, "KMS")
        return CaseOutcome(
            "CONFORMING_OBSERVED", "RELEASE_TWO_WORKERS_ON_THE_SAME_OPERATION_AND_OUTBOX_ROW",
            ["ONE_PREPARED_OWNER", "LOSER_ZERO_CALLS", "ONE_SIMULATED_APPLICATION_CALL", "RECEIPT_NOT_PROVIDER_EVENT_PROOF"],
            sha256_value(request), sha256_value(response), key_version, key_version, isolation, isolation,
        )
    if case_id == "M15":
        _managed_authority_commit(state, key_version)
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            _causal_binding(state, "OUTBOX_READY_BEFORE_ATTEMPT_CAS"),
        )
        state.event("WORKER_CRASHED_BEFORE_ATTEMPT_CAS")
        state = _restart(state)
        request = _kms_request(configuration)
        _prepare_attempt(state, "KMS", sha256_value(request), key_version)
        response = _kms_response(configuration, request)
        observed = _double_call(state, "KMS", request, response)
        require(observed is not None and _validate_kms(configuration, request, observed), "recovered response invalid")
        _mark_response_validated(state, "KMS", configuration, request, observed)
        _commit_receipt(state, "KMS")
        return CaseOutcome(
            "RECOVERED_BY_STRONG_LOOKUP", "CRASH_AFTER_SPANNER_OUTBOX_READY_COMMIT_BEFORE_ATTEMPT_CAS_AND_KMS_CALL",
            ["DURABLE_OUTBOX_RECOVERY", "NO_REAUTHORIZE", "NO_RECONSUME_CHALLENGE", "ONE_SIMULATED_APPLICATION_CALL"],
            sha256_value(request), sha256_value(response), key_version, key_version, isolation, isolation,
            final_state=state,
        )
    raise HarnessError(f"unsupported managed case {case_id}")


def _witness_lineage(state: SimulationState) -> str:
    return f"logical-lineage-{_operation_id(state)[:24]}"


def _witness_candidate(
    state: SimulationState,
    ledger: ExternalWitnessLedger,
    **overrides: Any,
) -> ExternalWitnessRecord:
    operation_id = _operation_id(state)
    if ledger.current_record is None:
        prior_cluster_id = "cluster-incumbent"
        prior_incarnation_id = "incarnation-incumbent"
        prior_revision_floor = 100
    else:
        prior_cluster_id = ledger.current_record.new_cluster_id
        prior_incarnation_id = ledger.current_record.new_incarnation_id
        prior_revision_floor = ledger.current_record.new_revision_floor
    snapshot_revision = prior_revision_floor - 10
    bump_revision = 1000 + ledger.generation
    values: dict[str, Any] = {
        "domain": WITNESS_DOMAIN,
        "authority_id": _framed_hash(WITNESS_DOMAIN, operation_id, "authority"),
        "prior_cluster_id": prior_cluster_id,
        "prior_incarnation_id": prior_incarnation_id,
        "prior_revision_floor": prior_revision_floor,
        "snapshot_sha256": _framed_hash(WITNESS_DOMAIN, operation_id, "snapshot", str(ledger.generation)),
        "snapshot_revision": snapshot_revision,
        "new_cluster_id": f"cluster-rebased-{operation_id[:16]}-g{ledger.generation + 1}",
        "new_incarnation_id": f"incarnation-rebased-{operation_id[16:32]}-g{ledger.generation + 1}",
        "new_revision_floor": snapshot_revision + bump_revision,
        "bump_revision": bump_revision,
        "mark_compacted": True,
        "rebase_authorization_sha256": _framed_hash(
            WITNESS_DOMAIN,
            operation_id,
            "rebase-authorization",
            str(ledger.generation + 1),
        ),
        "previous_record_sha256": ledger.current_sha256,
        "generation": ledger.generation + 1,
    }
    values.update(overrides)
    return ExternalWitnessRecord(**values)


def _self_hosted_case(
    case_id: str,
    repetition: int,
    state: SimulationState,
    configuration: dict[str, Any],
    fault_controller: OneShotFaultController,
) -> CaseOutcome:
    hosted = configuration["profiles"]["self_hosted"]
    key_version = hosted["key_version"]

    if case_id == "S00":
        request, response = _self_hosted_success(state, configuration)
        return CaseOutcome(
            "CONFORMING_OBSERVED", "NONE",
            ["LINEARIZABLE_AUTHORITY", "NON_NESTED_NONLEASED_CAS", "PREPARED_BEFORE_DOUBLE_CALL", "FULL_TRANSIT_VALIDATION"],
            sha256_value(request), sha256_value(response), key_version, key_version,
        )
    if case_id == "S01":
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            _causal_binding(state, "FOLLOWER_PARTITION_BOUNDARY"),
        )
        state.event("ETCD_FOLLOWER_ISOLATED", follower_state_accepted=False)
        if repetition % 2:
            state.event("ETCD_LINEARIZABLE_READ_REACHED_QUORUM")
            state.authority = "QUORUM_READ_OBSERVED"
            classification = "CONFORMING_OBSERVED"
            tokens = ["ISOLATED_FOLLOWER_STATE_REJECTED", "CURRENT_QUORUM_READ"]
        else:
            state.event("ETCD_LINEARIZABLE_READ_UNAVAILABLE_FAIL_CLOSED")
            state.authority = "REJECTED_FAIL_CLOSED"
            classification = "FAIL_CLOSED_REJECTED"
            tokens = ["ISOLATED_FOLLOWER_STATE_REJECTED", "NO_STALE_FALLBACK"]
        return CaseOutcome(classification, "ISOLATE_TARGET_FOLLOWER_FROM_QUORUM", tokens)
    if case_id == "S02":
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            _causal_binding(state, "SERIALIZABLE_READ_PROFILE"),
        )
        state.event("ETCD_SERIALIZABLE_READ_MODE_REJECTED", serializable=True)
        state.authority = "REJECTED_FAIL_CLOSED"
        return CaseOutcome(
            "FAIL_CLOSED_REJECTED", "ENABLE_SERIALIZABLE_READ_AGAINST_LAGGING_MEMBER",
            ["CANDIDATE_SERIALIZABLE_MODE_REJECTED_PREEXECUTION", "ZERO_DOUBLE_CALLS"],
        )
    if case_id == "S03":
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            _causal_binding(state, "DECODED_NESTED_TXN"),
        )
        _reject_preexecution_transition(
            state,
            "ETCD_NESTED_TRANSACTION_REJECTED",
            "NESTED_TRANSACTION_REJECTED_PREEXECUTION",
            key_version,
            nested=True,
        )
        state.authority = "REJECTED_FAIL_CLOSED"
        return CaseOutcome(
            "FAIL_CLOSED_REJECTED", "INSERT_NESTED_TXN_IN_SUCCESS_BRANCH",
            ["DECODED_NESTED_TXN_REJECTED_PREEXECUTION", "ZERO_DOUBLE_CALLS"],
        )
    if case_id == "S04":
        store = ExactKeyCASDouble.for_run(_operation_id(state))
        operation_record = store.operation_record(_operation_id(state), key_version)
        store.stage_delayed_commit(operation_record)
        state.database_attempts = 1
        state.event(
            "ETCD_REQUEST_ADMITTED_WITH_PENDING_COMMIT",
            operation_key=store.operation_key,
            delayed_record_sha256=sha256_value(operation_record),
        )
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            sha256_value(operation_record),
        )
        state.event(
            "ETCD_LEADER_REMOVED_AFTER_REQUEST_ADMISSION",
            operation_key=store.operation_key,
        )
        if repetition % 2:
            state.authority = "AUTHORIZED_COMMITTED"
            state.outbox = "SIGN_PENDING"
            state.challenge_consumptions = 1
            state.logical_sink_reservations = 1
            store.apply_delayed_commit(
                state,
                "ETCD_DELAYED_COMMIT_APPLIED_AFTER_ELECTION",
                kind="TRANSIT",
            )
            store.exact_read(
                state,
                "ETCD_EXACT_LINEARIZABLE_LOOKUP",
                consistency="LINEARIZABLE",
                expected_kind="EXACT_OPERATION_RECORD",
            )
            tokens = ["LEADER_ELECTION_NOT_ABORT_PROOF", "EXACT_RECORD_LINEARIZABLE_LOOKUP", "NO_BLIND_REISSUE"]
        else:
            require(
                store.exact_read(
                    state,
                    "ETCD_BARE_ABSENT_LINEARIZABLE_READ",
                    consistency="LINEARIZABLE",
                )
                is None,
                "self-hosted bare absent read drift",
            )
            store.cas_absent_to_terminal_fence(
                state,
                "ETCD_SAME_KEY_ABSENT_TO_TERMINAL_FENCE_CAS",
                kind="TRANSIT",
                consistency="LINEARIZABLE_TOP_LEVEL_CAS",
                operation_id=_operation_id(state),
                exact_key_version=key_version,
            )
            store.exact_read(
                state,
                "ETCD_CONFIRMING_LINEARIZABLE_READ",
                consistency="LINEARIZABLE",
                expected_kind="TERMINAL_FENCE",
            )
            store.release_delayed_commit(state, "ETCD_DELAYED_COMMIT_FENCE_CONFLICT")
            state.terminal_fence = "DURABLY_FENCED_ABSENCE"
            state.authority = "FENCED_ABSENT"
            tokens = ["LEADER_ELECTION_NOT_ABORT_PROOF", "BARE_ABSENCE_NONTERMINAL", "SAME_KEY_TERMINAL_FENCE", "CONFIRMING_LINEARIZABLE_READ"]
        return CaseOutcome(
            "RECOVERED_BY_STRONG_LOOKUP", "REMOVE_LEADER_AFTER_REQUEST_ADMISSION_BEFORE_OBSERVED_COMMIT", tokens,
        )
    if case_id in {"S05", "S06"}:
        _etcd_authority_commit(state, key_version)
        store = ExactKeyCASDouble.for_run(_operation_id(state))
        operation_record = store.operation_record(_operation_id(state), key_version)
        store.commit_now(operation_record)
        event = "ETCD_LEADER_LOST_POSTCOMMIT" if case_id == "S05" else "ETCD_TRANSACTION_ACK_DROPPED"
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            sha256_value(operation_record),
        )
        state.event(event)
        store.exact_read(
            state,
            "ETCD_EXACT_LINEARIZABLE_LOOKUP",
            consistency="LINEARIZABLE",
            expected_kind="EXACT_OPERATION_RECORD",
        )
        variant = (
            "REMOVE_LEADER_AFTER_COMMIT_BEFORE_RESPONSE"
            if case_id == "S05" else "DROP_TXN_RESPONSE_AFTER_COMMIT"
        )
        return CaseOutcome(
            "RECOVERED_BY_STRONG_LOOKUP", variant,
            ["EXACT_COMMITTED_OPERATION_RECOVERED", "NO_BLIND_REISSUE", "TOP_LEVEL_REVISION_ONLY"],
        )
    if case_id == "S07":
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            _causal_binding(state, "ETCD_QUORUM_PARTITION"),
        )
        state.event("ETCD_QUORUM_LOST", result="UNAVAILABLE")
        state.authority = "REJECTED_FAIL_CLOSED"
        return CaseOutcome(
            "FAIL_CLOSED_REJECTED", "PARTITION_MAJORITY_FROM_CLIENT",
            ["QUORUM_UNAVAILABLE", "NO_SERIALIZABLE_FALLBACK", "ZERO_DOUBLE_CALLS"],
        )
    if case_id == "S08":
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            _causal_binding(state, "WATCH_DELIVERY_DELAY"),
        )
        state.event("ETCD_WATCH_DELAYED", authority_use=False)
        state.event("ETCD_LINEARIZABLE_REVISION_ADVANCED")
        state.authority = "REJECTED_FAIL_CLOSED"
        return CaseOutcome(
            "FAIL_CLOSED_REJECTED", "DELAY_WATCH_WHILE_KV_REVISION_ADVANCES",
            ["WATCH_TELEMETRY_ONLY", "WATCH_CANNOT_AUTHORIZE", "WATCH_CANNOT_RESOLVE_AMBIGUITY"],
        )
    if case_id == "S09":
        variants = [
            "RESTORE_OLDER_SNAPSHOT_WITHOUT_BUMP",
            "RETURN_STALE_REPLAYED_OR_FORKED_WITNESS_RECORD",
            "MAKE_INDEPENDENT_WITNESS_UNAVAILABLE_OR_CAS_CONFLICT",
        ]
        variant = variants[(repetition - 1) % 3]
        ledger = ExternalWitnessLedger(_witness_lineage(state))
        if variant == "RETURN_STALE_REPLAYED_OR_FORKED_WITNESS_RECORD":
            prior = _witness_candidate(state, ledger)
            ledger.seed(prior)
        state.witness_record_sha256 = ledger.current_sha256
        state.witness_generation = ledger.generation
        candidate = _witness_candidate(state, ledger)
        witness_key = ledger.witness_key(
            candidate.authority_id,
            ledger.logical_cluster_lineage_id,
        )
        state.event(
            "EXTERNAL_WITNESS_LEDGER_OPENED",
            actor_domain=ledger.actor_domain,
            logical_cluster_lineage_id=ledger.logical_cluster_lineage_id,
            witness_key=witness_key,
            read_consistency="LINEARIZABLE",
            read_revision=ledger.generation,
            current_record_sha256=ledger.current_sha256,
            generation=ledger.generation,
            observed_record_sha256=ledger.current_sha256,
            observed_generation=ledger.generation,
            isolated_from_restore_snapshot=True,
        )
        if variant == "RESTORE_OLDER_SNAPSHOT_WITHOUT_BUMP":
            candidate_values = candidate.as_dict()
            candidate_values.update(
                bump_revision=0,
                new_revision_floor=candidate.snapshot_revision,
                mark_compacted=False,
            )
            candidate = ExternalWitnessRecord(**candidate_values)
        elif variant == "RETURN_STALE_REPLAYED_OR_FORKED_WITNESS_RECORD":
            candidate_values = candidate.as_dict()
            candidate_values.update(
                previous_record_sha256=ZERO_SHA256,
                generation=ledger.generation,
            )
            candidate = ExternalWitnessRecord(**candidate_values)
        else:
            ledger.available = False
        state.event(
            "RESTORE_WITNESS_CANDIDATE_STAGED",
            witness_record_sha256=sha256_value(candidate.as_dict()),
            snapshot_sha256=candidate.snapshot_sha256,
        )
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            sha256_value(candidate.as_dict()),
        )
        before_sha = ledger.current_sha256
        before_generation = ledger.generation
        applied = ledger.compare_and_swap(
            state,
            candidate,
            caller_actor_domain=WITNESS_ACTOR_DOMAIN,
            expected_previous_record_sha256=candidate.previous_record_sha256,
            expected_generation=max(candidate.generation - 1, 0),
            event_name="EXTERNAL_WITNESS_VALIDATION_FAILED",
        )
        require(not applied, "invalid restore witness was committed")
        require(
            ledger.current_sha256 == before_sha and ledger.generation == before_generation,
            "failed witness CAS mutated ledger",
        )
        state.restore = "INCIDENT_QUARANTINED"
        state.watch = "INVALIDATED"
        state.cache = "DISCARDED"
        state.event(
            "RESTORED_CLUSTER_INCIDENT_QUARANTINED",
            variant=variant,
            witness_record_sha256=ledger.current_sha256,
            witness_generation=ledger.generation,
        )
        return CaseOutcome(
            "INCIDENT_QUARANTINED", variant,
            ["INDEPENDENT_WITNESS_DOMAIN", "INVALID_WITNESS_FAILS_CLOSED", "NO_INCUMBENT_EPOCH_REJOIN"],
        )
    if case_id == "S10":
        ledger = ExternalWitnessLedger(_witness_lineage(state))
        candidate = _witness_candidate(state, ledger)
        witness_key = ledger.witness_key(
            candidate.authority_id,
            ledger.logical_cluster_lineage_id,
        )
        state.event(
            "EXTERNAL_WITNESS_LEDGER_OPENED",
            actor_domain=ledger.actor_domain,
            logical_cluster_lineage_id=ledger.logical_cluster_lineage_id,
            witness_key=witness_key,
            read_consistency="LINEARIZABLE",
            read_revision=ledger.generation,
            current_record_sha256=ledger.current_sha256,
            generation=ledger.generation,
            observed_record_sha256=ledger.current_sha256,
            observed_generation=ledger.generation,
            isolated_from_restore_snapshot=True,
        )
        state.event(
            "SNAPSHOT_HASH_VERIFIED",
            snapshot_sha256=candidate.snapshot_sha256,
            snapshot_revision=candidate.snapshot_revision,
            skip_hash_check=False,
        )
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            candidate.snapshot_sha256,
        )
        candidate_values = candidate.as_dict()
        if repetition % 2:
            candidate_values["new_incarnation_id"] = candidate.prior_incarnation_id
            rejection_variant = "INCUMBENT_INCARNATION_REUSED"
        else:
            candidate_values["previous_record_sha256"] = "f" * 64
            rejection_variant = "WITNESS_PREVIOUS_HASH_MISMATCH"
        candidate = ExternalWitnessRecord(**candidate_values)
        applied = ledger.compare_and_swap(
            state,
            candidate,
            caller_actor_domain=WITNESS_ACTOR_DOMAIN,
            expected_previous_record_sha256=candidate.previous_record_sha256,
            expected_generation=0,
            event_name="RESTORE_IDENTITY_OR_WITNESS_BINDING_REJECTED",
        )
        require(not applied and ledger.current_record is None, "invalid restore identity was committed")
        state.restore = "INCIDENT_QUARANTINED"
        state.watch = "INVALIDATED"
        state.cache = "DISCARDED"
        state.event(
            "RESTORED_CLUSTER_INCIDENT_QUARANTINED",
            variant=rejection_variant,
            witness_record_sha256=ledger.current_sha256,
            witness_generation=ledger.generation,
        )
        return CaseOutcome(
            "INCIDENT_QUARANTINED", "RESTORE_WITH_BUMP_BUT_REUSE_INCUMBENT_INCARNATION_PIN_OR_MISMATCH_WITNESS_BINDING",
            ["BUMP_NOT_SELF_AUTHORIZING", "NEW_IDENTITY_REQUIRED", "EXACT_WITNESS_BINDING_REQUIRED"],
        )
    if case_id == "S11":
        ledger = ExternalWitnessLedger(_witness_lineage(state))
        candidate = _witness_candidate(state, ledger)
        witness_key = ledger.witness_key(
            candidate.authority_id,
            ledger.logical_cluster_lineage_id,
        )
        state.event(
            "EXTERNAL_WITNESS_LEDGER_OPENED",
            actor_domain=ledger.actor_domain,
            logical_cluster_lineage_id=ledger.logical_cluster_lineage_id,
            witness_key=witness_key,
            read_consistency="LINEARIZABLE",
            read_revision=ledger.generation,
            current_record_sha256=ledger.current_sha256,
            generation=ledger.generation,
            observed_record_sha256=ledger.current_sha256,
            observed_generation=ledger.generation,
            isolated_from_restore_snapshot=True,
        )
        state.event(
            "SNAPSHOT_HASH_VERIFIED",
            snapshot_sha256=candidate.snapshot_sha256,
            snapshot_revision=candidate.snapshot_revision,
            skip_hash_check=False,
        )
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            candidate.snapshot_sha256,
        )
        state.event(
            "RESTORE_REVISION_BUMPED_AND_MARKED_COMPACTED",
            prior_revision_floor=candidate.prior_revision_floor,
            snapshot_revision=candidate.snapshot_revision,
            bump_revision=candidate.bump_revision,
            new_revision_floor=candidate.new_revision_floor,
            mark_compacted=candidate.mark_compacted,
        )
        applied = ledger.compare_and_swap(
            state,
            candidate,
            caller_actor_domain=WITNESS_ACTOR_DOMAIN,
            expected_previous_record_sha256=ZERO_SHA256,
            expected_generation=0,
            event_name="EXTERNAL_WITNESS_EXACT_CAS_COMMITTED",
        )
        require(applied, "valid external witness CAS rejected")
        state.event(
            "ALL_PRE_RESTORE_WATCHES_INVALIDATED",
            new_cluster_id=candidate.new_cluster_id,
            new_incarnation_id=candidate.new_incarnation_id,
        )
        state.event(
            "FULL_LINEARIZABLE_CACHE_REBUILD_COMPLETED",
            new_cluster_id=candidate.new_cluster_id,
            revision_floor=candidate.new_revision_floor,
        )
        state.restore = "REBASED_NEW_INCARNATION"
        state.watch = "INVALIDATED"
        state.cache = "FULL_LINEARIZABLE_REBUILD"
        state.restore_cluster_id = candidate.new_cluster_id
        state.restore_incarnation_id = candidate.new_incarnation_id
        state.restore_revision_floor = candidate.new_revision_floor
        return CaseOutcome(
            "REBASED_NEW_INCARNATION", "RESTORE_WITH_BUMP_MARK_COMPACTED_AND_NEW_INCARNATION",
            ["VERIFIED_SNAPSHOT", "REVISION_BUMP_MARK_COMPACTED", "INDEPENDENT_WITNESS_EXACT_CAS", "NEW_CLUSTER_AND_INCARNATION", "WATCH_INVALIDATED", "FULL_LINEARIZABLE_REBUILD"],
        )
    if case_id == "S12":
        operation_id = _operation_id(state)
        cluster_id = f"cluster-double-{operation_id[:16]}"
        request_id = f"request-double-{operation_id[16:40]}"
        success = repetition % 2 == 1
        audit_record_sha256 = (
            _framed_hash(
                "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/s12-audit",
                operation_id,
                cluster_id,
                request_id,
                "node-active-a",
                "node-standby-b",
            )
            if success
            else None
        )
        wire_attempt_sha256 = (
            _framed_hash(
                "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/s12-wire-attempt",
                operation_id,
                cluster_id,
                request_id,
                "node-standby-b",
            )
            if success
            else None
        )
        correlation = S12ExecutionCorrelation(
            target_node="node-active-a",
            route_node="node-active-a",
            executing_node="node-standby-b" if success else None,
            executing_ha_role="PERFORMANCE_STANDBY_ACTIVE" if success else None,
            cluster_id=cluster_id,
            request_id=request_id,
            redirect_node="node-standby-b" if success else None,
            forwarded_by_node="node-active-a" if success else None,
            audit_record_sha256=audit_record_sha256,
            wire_attempt_sha256=wire_attempt_sha256,
            redirect_forward_audit_bound=success,
        )
        correlation.validate(success=success)
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            _causal_binding(state, "ACTIVE_NODE_BEFORE_SEAL"),
        )
        state.event(
            "OPENBAO_DIRECT_TARGET_SEAL_STATUS",
            target_node="node-active-a",
            cluster_id=cluster_id,
            target_ha_role="ACTIVE",
            sealed=True,
            service_wide_unavailable_inferred=False,
        )
        state.event(
            "OPENBAO_ROUTE_EXECUTION_EVIDENCE",
            **correlation.event_details(),
        )
        if success:
            request, response = _self_hosted_success(
                state,
                configuration,
                correlation=correlation,
            )
            classification = "CONFORMING_OBSERVED"
            tokens = [
                "TARGET_AND_EXECUTING_NODE_SEPARATE",
                "SUCCESS_BRANCH_EXPLICIT_VERSION",
                "SUCCESS_BRANCH_EXACT_MESSAGE_AND_PIN",
                "SUCCESS_BRANCH_OFFLINE_VERIFY",
                "SUCCESS_BRANCH_DURABLE_RECEIPT",
                "NO_SERVICE_WIDE_FAILURE_INFERENCE",
            ]
            return CaseOutcome(
                classification, "SEALED_ACTIVE_WITH_VALIDATED_STANDBY_TAKEOVER", tokens,
                sha256_value(request), sha256_value(response), key_version, key_version,
            )
        state.authority = "REJECTED_FAIL_CLOSED"
        state.event(
            "OPENBAO_STANDBY_TAKEOVER_UNAVAILABLE_FAIL_CLOSED",
            cluster_id=cluster_id,
            request_id=request_id,
            accepted_receipts=0,
            emitted_outputs=0,
        )
        return CaseOutcome(
            "FAIL_CLOSED_REJECTED", "SEALED_ACTIVE_WITH_NO_VALIDATED_SUCCESSOR_RESPONSE",
            ["TARGET_AND_EXECUTING_NODE_SEPARATE", "FAIL_BRANCH_ZERO_ACCEPTED_RECEIPT", "FAIL_BRANCH_ZERO_OUTPUT", "NO_SERVICE_WIDE_FAILURE_INFERENCE"],
        )
    if case_id == "S13":
        _etcd_authority_commit(state, key_version)
        request = _transit_request(configuration)
        _prepare_attempt(state, "TRANSIT", sha256_value(request), key_version)
        response = _transit_response(configuration)
        require(
            _double_call(
                state,
                "TRANSIT",
                request,
                response,
                drop_response=True,
                fault_controller=fault_controller,
                fault_cut=fault_controller.injection_cut,
            )
            is None,
            "Transit drop fault failed",
        )
        _quarantine(state, "TRANSIT")
        state = _restart(state)
        return CaseOutcome(
            "AMBIGUOUS_QUARANTINED", "DROP_TRANSIT_RESPONSE_AFTER_SIGN_PROCESSING_THEN_RESTART_WORKER",
            ["DURABLE_PREPARED_MARKER", "LOST_RESPONSE_NOT_NO_SIGN_PROOF", "TERMINAL_QUARANTINE", "RESTART_NO_RESIGN"],
            sha256_value(request), ZERO_SHA256, key_version, 0,
            final_state=state,
        )
    if case_id == "S14":
        _etcd_authority_commit(state, key_version)
        request = _transit_request(configuration)
        _prepare_attempt(state, "TRANSIT", sha256_value(request), key_version)
        response = _transit_response(configuration)
        observed = _double_call(state, "TRANSIT", request, response)
        require(observed is not None and _validate_transit(configuration, request, observed), "valid Transit response missing")
        _mark_response_validated(state, "TRANSIT", configuration, request, observed)
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            state.validation_binding_sha256,
        )
        state.event("ETCD_RECEIPT_PERSIST_OUTCOME_UNKNOWN")
        if repetition % 2:
            _commit_receipt(state, "TRANSIT")
            state.event(
                "ETCD_LINEARIZABLE_EXACT_RECEIPT_LOOKUP",
                result="EXACT_RECEIPT",
                operation_id=state.prepared_operation_id,
                receipt_binding_sha256=state.receipt_binding_sha256,
            )
            classification = "RECOVERED_BY_STRONG_LOOKUP"
            tokens = ["IN_MEMORY_SIGNATURE_NOT_DURABLE", "EXACT_RECEIPT_RECOVERED", "RESTART_NO_RESIGN"]
        else:
            state.event(
                "ETCD_LINEARIZABLE_EXACT_RECEIPT_LOOKUP",
                result="ABSENT",
                operation_id=state.prepared_operation_id,
                receipt_binding_sha256=ZERO_SHA256,
            )
            _quarantine(state, "TRANSIT")
            classification = "AMBIGUOUS_QUARANTINED"
            tokens = ["IN_MEMORY_SIGNATURE_NOT_DURABLE", "ABSENT_RECEIPT_QUARANTINED", "RESTART_NO_RESIGN"]
        state = _restart(state)
        return CaseOutcome(
            classification, "FAIL_ETCD_PERSIST_AFTER_SIGNATURE_VALIDATION_THEN_RESTART_WORKER", tokens,
            sha256_value(request), sha256_value(response), key_version,
            key_version,
            final_state=state,
        )
    if case_id == "S15":
        _etcd_authority_commit(state, key_version)
        request = _transit_request(configuration)
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            sha256_value(request),
        )
        state.event("OPENBAO_KEY_ROTATED", frozen_version=key_version, latest_version=key_version + 1)
        if repetition % 2:
            _prepare_attempt(state, "TRANSIT", sha256_value(request), key_version)
            response = _transit_response(configuration)
            observed = _double_call(state, "TRANSIT", request, response)
            require(observed is not None and _validate_transit(configuration, request, observed), "pinned version response invalid")
            _mark_response_validated(state, "TRANSIT", configuration, request, observed)
            _commit_receipt(state, "TRANSIT")
            return CaseOutcome(
                "CONFORMING_OBSERVED", "ROTATE_KEY_PINNED_VERSION_REMAINS_AVAILABLE",
                ["EXPLICIT_FROZEN_VERSION", "LATEST_NOT_SUBSTITUTED", "FULL_TRANSIT_VALIDATION"],
                sha256_value(request), sha256_value(response), key_version, key_version,
            )
        state.attempt = "REJECTED_FAIL_CLOSED"
        _commit_durable_transition(
            state,
            "TRANSIT",
            "PRE_ATTEMPT_REJECTED_FAIL_CLOSED",
            key_version,
            "OPENBAO_PINNED_VERSION_UNAVAILABLE_REJECTED",
            latest_substitution=False,
        )
        return CaseOutcome(
            "FAIL_CLOSED_REJECTED", "ROTATE_KEY_PINNED_VERSION_UNAVAILABLE",
            ["EXPLICIT_FROZEN_VERSION", "LATEST_NOT_SUBSTITUTED", "ZERO_DOUBLE_CALLS"],
            sha256_value(request), ZERO_SHA256, key_version, 0,
        )
    if case_id == "S16":
        _etcd_authority_commit(state, key_version)
        request = _transit_request(configuration)
        fault_controller.trigger(
            state,
            fault_controller.injection_cut,
            sha256_value(request),
        )
        request["key_version"] = 0
        state.attempt = "REJECTED_FAIL_CLOSED"
        _commit_durable_transition(
            state,
            "TRANSIT",
            "PRE_ATTEMPT_REJECTED_FAIL_CLOSED",
            key_version,
            "TRANSIT_ZERO_VERSION_REJECTED_BEFORE_ATTEMPT",
        )
        return CaseOutcome(
            "FAIL_CLOSED_REJECTED", "SET_KEY_VERSION_TO_ZERO",
            ["ZERO_OR_OMITTED_VERSION_REJECTED", "LATEST_NOT_SELECTED", "ZERO_DOUBLE_CALLS"],
            sha256_value(request), ZERO_SHA256, 0, 0,
        )
    if case_id == "S17":
        variants = ["MUTATE_SIGNATURE_VERSION_PREFIX", "MUTATE_PUBLIC_KEY_PIN", "MUTATE_MESSAGE"]
        variant = variants[(repetition - 1) % 3]
        _etcd_authority_commit(state, key_version)
        request = _transit_request(configuration)
        if variant == "MUTATE_MESSAGE":
            fault_controller.trigger(
                state,
                fault_controller.injection_cut,
                sha256_value(request),
            )
            request["input"] = base64.b64encode(MESSAGE[:-1] + bytes([MESSAGE[-1] ^ 1])).decode("ascii")
        _prepare_attempt(state, "TRANSIT", sha256_value(request), key_version)
        response = _transit_response(configuration)
        validation_configuration = configuration
        evidence_public_key_sha256 = PUBLIC_KEY_SHA256
        if variant != "MUTATE_MESSAGE":
            fault_controller.trigger(
                state,
                fault_controller.injection_cut,
                sha256_value(response),
            )
        if variant == "MUTATE_SIGNATURE_VERSION_PREFIX":
            response["signature"] = response["signature"].replace(f"vault:v{key_version}:", f"vault:v{key_version + 1}:", 1)
        elif variant == "MUTATE_PUBLIC_KEY_PIN":
            validation_configuration = json.loads(canonical_bytes(configuration))
            mutated_public_key = bytearray(
                bytes.fromhex(
                    validation_configuration["profiles"]["self_hosted"][
                        "public_key_hex"
                    ]
                )
            )
            mutated_public_key[-1] ^= 1
            validation_configuration["profiles"]["self_hosted"][
                "public_key_hex"
            ] = bytes(mutated_public_key).hex()
            evidence_public_key_sha256 = sha256_bytes(bytes(mutated_public_key))
        observed = _double_call(state, "TRANSIT", request, response)
        require(
            observed is not None
            and not _validate_transit(
                validation_configuration, request, observed
            ),
            "negative Transit response unexpectedly valid",
        )
        _fail_response_validation(state, "TRANSIT", "SIGNATURE_BINDING_MISMATCH")
        return CaseOutcome(
            "FAIL_CLOSED_REJECTED", variant,
            ["SINGLE_NONBATCH_CONTEXT_FREE_REQUEST", "EXACT_VERSION_PREFIX", "PINNED_KEY_AND_MESSAGE", "INVALID_BINDING_REJECTED"],
            sha256_value(request), sha256_value(response), key_version, 0,
            evidence_public_key_sha256=evidence_public_key_sha256,
        )
    raise HarnessError(f"unsupported self-hosted case {case_id}")


GLOBAL_INVARIANT_IDS = tuple(f"X{index:02d}" for index in range(1, 9))
STATE_FIELDS = set(SimulationState().snapshot())
EVENT_DETAIL_KEYS: dict[str, frozenset[str]] = {
    "ALL_PRE_RESTORE_WATCHES_INVALIDATED": frozenset({"new_cluster_id", "new_incarnation_id"}),
    "ASSIGNMENT_HASH_SEALED": frozenset({"assignment_sha256", "simulation_run_id"}),
    "CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM": frozenset({"assignment_sha256", "case_id"}),
    "CONTROL_NO_FAULT_TRIGGERED": frozenset({"case_id", "trigger_count"}),
    "DURABLE_IMAGE_SERIALIZED": frozenset({"durable_image", "image_sha256"}),
    "EPHEMERAL_WORKER_DESTROYED": frozenset(),
    "ETCD_BARE_ABSENT_LINEARIZABLE_READ": frozenset({"consistency", "operation_key", "record_sha256", "result", "revision", "terminal"}),
    "ETCD_CONFIRMING_LINEARIZABLE_READ": frozenset({"consistency", "operation_key", "record_sha256", "result", "revision", "terminal"}),
    "ETCD_DELAYED_COMMIT_APPLIED_AFTER_ELECTION": frozenset({"cas_result", "operation_key", "record_sha256", "revision"}),
    "ETCD_DELAYED_COMMIT_FENCE_CONFLICT": frozenset({"cas_result", "compare_record_sha256", "delayed_record_sha256", "observed_record_sha256", "operation_key", "revision"}),
    "ETCD_EXACT_LINEARIZABLE_LOOKUP": frozenset({"consistency", "operation_key", "record_sha256", "result", "revision", "terminal"}),
    "ETCD_FOLLOWER_ISOLATED": frozenset({"follower_state_accepted"}),
    "ETCD_LEADER_LOST_POSTCOMMIT": frozenset(),
    "ETCD_LEADER_REMOVED_AFTER_REQUEST_ADMISSION": frozenset({"operation_key"}),
    "ETCD_LINEARIZABLE_EXACT_RECEIPT_LOOKUP": frozenset({"operation_id", "receipt_binding_sha256", "result"}),
    "ETCD_LINEARIZABLE_READ_REACHED_QUORUM": frozenset(),
    "ETCD_LINEARIZABLE_READ_UNAVAILABLE_FAIL_CLOSED": frozenset(),
    "ETCD_LINEARIZABLE_REVISION_ADVANCED": frozenset(),
    "ETCD_NESTED_TRANSACTION_REJECTED": frozenset({"nested"}),
    "ETCD_OUTBOX_COMMITTED": frozenset({"outbox"}),
    "ETCD_QUORUM_LOST": frozenset({"result"}),
    "ETCD_RECEIPT_PERSIST_OUTCOME_UNKNOWN": frozenset(),
    "ETCD_REQUEST_ADMITTED_WITH_PENDING_COMMIT": frozenset({"delayed_record_sha256", "operation_key"}),
    "ETCD_SAME_KEY_ABSENT_TO_TERMINAL_FENCE_CAS": frozenset({"cas_result", "committed_record_sha256", "compare_record_sha256", "consistency", "operation_key", "revision"}),
    "ETCD_SERIALIZABLE_READ_MODE_REJECTED": frozenset({"serializable"}),
    "ETCD_TOP_LEVEL_CAS": frozenset({"leased", "nested", "response_revision_source", "serializable"}),
    "ETCD_TRANSACTION_ACK_DROPPED": frozenset(),
    "ETCD_WATCH_DELAYED": frozenset({"authority_use"}),
    "EXTERNAL_WITNESS_LEDGER_OPENED": frozenset({
        "actor_domain", "current_record_sha256", "generation",
        "isolated_from_restore_snapshot", "logical_cluster_lineage_id",
        "observed_generation", "observed_record_sha256", "read_consistency",
        "read_revision", "witness_key",
    }),
    "FULL_LINEARIZABLE_CACHE_REBUILD_COMPLETED": frozenset({"new_cluster_id", "revision_floor"}),
    "LOSING_WORKER_ATTEMPT_CAS_CONFLICT": frozenset({"simulated_calls"}),
    "NEW_WORKER_CONSTRUCTED_FROM_DURABLE_IMAGE": frozenset({"prior_worker_ephemeral_state_reused", "state_object_reused"}),
    "ONE_SHOT_FAULT_CONTROLLER_ARMED": frozenset({"assignment_sha256", "case_id", "injection_cut", "injection_variant", "trigger_limit"}),
    "ONE_SHOT_FAULT_TRIGGERED": frozenset({"case_id", "causal_binding_sha256", "injection_cut", "injection_variant", "trigger_count"}),
    "OPENBAO_DIRECT_TARGET_SEAL_STATUS": frozenset({"cluster_id", "sealed", "service_wide_unavailable_inferred", "target_ha_role", "target_node"}),
    "OPENBAO_KEY_ROTATED": frozenset({"frozen_version", "latest_version"}),
    "OPENBAO_PINNED_VERSION_UNAVAILABLE_REJECTED": frozenset({"latest_substitution"}),
    "OPENBAO_ROUTE_EXECUTION_EVIDENCE": frozenset({"audit_record_sha256", "cluster_id", "executing_ha_role", "executing_node", "forwarded_by_node", "redirect_forward_audit_bound", "redirect_node", "request_id", "route_node", "target_node", "wire_attempt_sha256"}),
    "OPENBAO_STANDBY_TAKEOVER_UNAVAILABLE_FAIL_CLOSED": frozenset({"accepted_receipts", "cluster_id", "emitted_outputs", "request_id"}),
    "RESTART_NO_RESIGN_CONFIRMED": frozenset({"calls_after_restart"}),
    "RESTORED_CLUSTER_INCIDENT_QUARANTINED": frozenset({"variant", "witness_generation", "witness_record_sha256"}),
    "RESTORE_REVISION_BUMPED_AND_MARKED_COMPACTED": frozenset({"bump_revision", "mark_compacted", "new_revision_floor", "prior_revision_floor", "snapshot_revision"}),
    "RESTORE_WITNESS_CANDIDATE_STAGED": frozenset({"snapshot_sha256", "witness_record_sha256"}),
    "SNAPSHOT_HASH_VERIFIED": frozenset({"skip_hash_check", "snapshot_revision", "snapshot_sha256"}),
    "SPANNER_ABSENT_TO_TERMINAL_FENCE_TRANSACTION": frozenset({"cas_result", "committed_record_sha256", "compare_record_sha256", "consistency", "operation_key", "revision"}),
    "SPANNER_BARE_ABSENT_STRONG_READ": frozenset({"consistency", "operation_key", "record_sha256", "result", "revision", "terminal"}),
    "SPANNER_CLOSURE_SIDE_EFFECT_SENTINEL_REJECTED": frozenset({"attempted"}),
    "SPANNER_COMMIT_ADMITTED_OUTCOME_UNRESOLVED": frozenset({"delayed_record_sha256", "operation_key"}),
    "SPANNER_COMMIT_RESPONSE_LOST": frozenset({"operation_key", "record_sha256", "server_commit"}),
    "SPANNER_CONFIRMING_STRONG_READ": frozenset({"consistency", "operation_key", "record_sha256", "result", "revision", "terminal"}),
    "SPANNER_DEFINITE_ABORT": frozenset({"attempt"}),
    "SPANNER_DELAYED_COMMIT_FENCE_CONFLICT": frozenset({"cas_result", "compare_record_sha256", "delayed_record_sha256", "observed_record_sha256", "operation_key", "revision"}),
    "SPANNER_EXACT_STRONG_LOOKUP": frozenset({"consistency", "operation_key", "record_sha256", "result", "revision", "terminal"}),
    "SPANNER_ISOLATION_PROFILE_REJECTED": frozenset({"requested", "required"}),
    "SPANNER_OUTBOX_COMMITTED": frozenset({"outbox"}),
    "SPANNER_RECEIPT_PERSIST_OUTCOME_UNKNOWN": frozenset(),
    "SPANNER_SERIALIZABLE_TRANSACTION_ATTEMPT": frozenset({"attempt", "closure_scope"}),
    "SPANNER_SERVER_COMMIT_APPLIED": frozenset({"operation_key", "record_sha256", "revision"}),
    "SPANNER_STRONG_EXACT_RECEIPT_LOOKUP": frozenset({"operation_id", "receipt_binding_sha256", "result"}),
    "TRANSIT_ZERO_VERSION_REJECTED_BEFORE_ATTEMPT": frozenset(),
    "TWO_WORKERS_RELEASED": frozenset({"workers"}),
    "WORKER_CRASHED_BEFORE_ATTEMPT_CAS": frozenset(),
    "WORKER_RESTARTED": frozenset({"calls_before_restart", "durable_attempt_state"}),
}
_WITNESS_EVENT_KEYS = frozenset({
    "actor_domain", "caller_actor_domain", "cas_result", "expected_generation",
    "expected_previous_record_sha256", "observed_generation",
    "logical_cluster_lineage_id", "observed_previous_record_sha256",
    "observed_witness_key", "rejection_reason",
    "witness_key", "witness_record", "witness_record_sha256",
})
for _event_name in (
    "EXTERNAL_WITNESS_EXACT_CAS_COMMITTED",
    "EXTERNAL_WITNESS_VALIDATION_FAILED",
    "RESTORE_IDENTITY_OR_WITNESS_BINDING_REJECTED",
):
    EVENT_DETAIL_KEYS[_event_name] = _WITNESS_EVENT_KEYS
_CALL_EVENT_KEYS = frozenset({
    "attempt_sequence", "audit_record_sha256", "call_binding_sha256", "evidence_class",
    "executing_node", "execution_cluster_id", "execution_request_id", "hidden_retries",
    "key_version", "message_sha256", "operation_id", "prepared_record_sha256",
    "public_key_sha256", "request_sha256", "wire_attempt_sha256",
})
_VALIDATION_EVENT_KEYS = frozenset({
    "audit_record_sha256", "call_binding_sha256", "executing_node", "execution_cluster_id",
    "execution_request_id", "key_version", "message_bytes", "message_sha256",
    "operation_id", "public_key_sha256", "request_sha256", "response_sha256",
    "validation_binding_sha256", "wire_attempt_sha256",
})
_RECEIPT_EVENT_KEYS = frozenset({
    "audit_record_sha256", "call_binding_sha256", "executing_node", "execution_cluster_id",
    "execution_request_id", "key_version", "message_sha256", "operation_id",
    "prepared_record_sha256", "public_key_sha256", "receipt_binding_sha256",
    "request_sha256", "response_sha256", "validation_binding_sha256",
    "wire_attempt_sha256",
})
for _kind in ("KMS", "TRANSIT"):
    EVENT_DETAIL_KEYS.update({
        f"{_kind}_AMBIGUOUS_QUARANTINED": frozenset({"call_binding_sha256", "operation_id", "prepared_record_sha256", "validation_binding_sha256"}),
        f"{_kind}_DOUBLE_CALL": _CALL_EVENT_KEYS,
        f"{_kind}_DOUBLE_PROCESSING_COMPLETED": frozenset({"call_binding_sha256", "response_sha256"}),
        f"{_kind}_DOUBLE_RESPONSE_DROPPED": frozenset({"call_binding_sha256", "response_sha256"}),
        f"{_kind}_DOUBLE_RESPONSE_OBSERVED": frozenset({"call_binding_sha256", "response_sha256"}),
        f"{_kind}_RESPONSE_FULLY_VALIDATED": _VALIDATION_EVENT_KEYS,
        f"{_kind}_RESPONSE_REJECTED": frozenset({"call_binding_sha256", "operation_id", "prepared_record_sha256", "reason"}),
        f"{_kind}_SIGNATURE_RECEIPT_COMMITTED": _RECEIPT_EVENT_KEYS,
        f"{_kind}_SIGN_ATTEMPT_PREPARED": frozenset({"durable", "prepared_record", "prepared_record_sha256"}),
    })
EVENT_DETAIL_KEYS.update({
    "KMS_REQUEST_REJECTED_BEFORE_ATTEMPT": frozenset({"reason"}),
    "KMS_RESOURCE_REJECTED_BEFORE_ATTEMPT": frozenset({"variant"}),
})
_TRANSITION_COMMIT_EVENT_KEYS = frozenset({
    "transition_envelope", "transition_record", "transition_record_sha256",
})
EVENT_DETAIL_KEYS["SPANNER_OUTBOX_COMMITTED"] = frozenset(
    {"outbox"} | set(_TRANSITION_COMMIT_EVENT_KEYS)
)
EVENT_DETAIL_KEYS["ETCD_TOP_LEVEL_CAS"] = frozenset(
    {
        "leased", "nested", "response_revision_source", "serializable",
    }
    | set(_TRANSITION_COMMIT_EVENT_KEYS)
)
EVENT_DETAIL_KEYS["ETCD_NESTED_TRANSACTION_REJECTED"] = frozenset({
    "nested", "transition_envelope",
})
for _event_name in (
    "SPANNER_SERVER_COMMIT_APPLIED",
    "ETCD_DELAYED_COMMIT_APPLIED_AFTER_ELECTION",
    "SPANNER_ABSENT_TO_TERMINAL_FENCE_TRANSACTION",
    "ETCD_SAME_KEY_ABSENT_TO_TERMINAL_FENCE_CAS",
):
    EVENT_DETAIL_KEYS[_event_name] = frozenset(
        set(EVENT_DETAIL_KEYS[_event_name]) | set(_TRANSITION_COMMIT_EVENT_KEYS)
    )
for _kind in ("KMS", "TRANSIT"):
    EVENT_DETAIL_KEYS[f"{_kind}_SIGN_ATTEMPT_PREPARED"] = frozenset(
        {"durable", "prepared_record", "prepared_record_sha256"}
        | set(_TRANSITION_COMMIT_EVENT_KEYS)
    )
    EVENT_DETAIL_KEYS[f"{_kind}_SIGN_ATTEMPT_CALL_CONSUMED"] = (
        _TRANSITION_COMMIT_EVENT_KEYS
    )
    EVENT_DETAIL_KEYS[f"{_kind}_SIGNATURE_RECEIPT_COMMITTED"] = frozenset(
        set(_RECEIPT_EVENT_KEYS) | set(_TRANSITION_COMMIT_EVENT_KEYS)
    )
    EVENT_DETAIL_KEYS[f"{_kind}_AMBIGUOUS_QUARANTINED"] = frozenset(
        {
            "call_binding_sha256", "operation_id", "prepared_record_sha256",
            "validation_binding_sha256",
        }
        | set(_TRANSITION_COMMIT_EVENT_KEYS)
    )
    EVENT_DETAIL_KEYS[f"{_kind}_RESPONSE_REJECTED"] = frozenset(
        {"call_binding_sha256", "operation_id", "prepared_record_sha256", "reason"}
        | set(_TRANSITION_COMMIT_EVENT_KEYS)
    )
for _event_name in (
    "KMS_REQUEST_REJECTED_BEFORE_ATTEMPT",
    "KMS_RESOURCE_REJECTED_BEFORE_ATTEMPT",
    "OPENBAO_PINNED_VERSION_UNAVAILABLE_REJECTED",
    "TRANSIT_ZERO_VERSION_REJECTED_BEFORE_ATTEMPT",
):
    EVENT_DETAIL_KEYS[_event_name] = frozenset(
        set(EVENT_DETAIL_KEYS[_event_name]) | set(_TRANSITION_COMMIT_EVENT_KEYS)
    )
RUN_ROW_FIELDS = {
    "schema",
    "harness_mode",
    "evidence_class",
    "row_kind",
    "counts_toward_experiment",
    "counts_toward_harness_conformance",
    "experimental_run_row",
    "contract_sha256",
    "schedule",
    "case",
    "row_outcome",
    "case_classification",
    "simulated_classification",
    "classification_scope",
    "oracle_classification_allowed",
    "explicit_invariant_ids",
    "branch_invariant_ids",
    "effective_invariant_ids",
    "state",
    "event_trace",
    "evidence",
    "assertions",
    "boundary",
    "claim_ceiling",
    "forbidden_claims",
    "retained",
}
EVIDENCE_FIELDS = {
    "effective_isolation",
    "emitted_outputs",
    "message_bytes",
    "message_sha256",
    "post_state_sha256",
    "pre_state_sha256",
    "provider_evidence_sha256",
    "public_key_sha256",
    "real_provider_calls",
    "request_sha256",
    "requested_isolation",
    "requested_key_version",
    "response_sha256",
    "restarts",
    "semantic_tokens",
    "simulated_application_calls",
    "simulated_processing_events",
    "simulator_trace_sha256",
    "test_signature_sha256",
    "validated_key_version",
}


def _contract_index(contract: dict[str, Any]) -> dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]]:
    result: dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]] = {}
    for track in contract["tracks"]:
        for case in track["cases"]:
            result[(track["track_id"], case["case_id"])] = (track, case)
    return result


def _event_order_assertions(state: SimulationState) -> tuple[bool, bool]:
    prepared = [
        event["sequence"]
        for event in state.events
        if event["name"].endswith("_SIGN_ATTEMPT_PREPARED")
    ]
    calls = [
        event["sequence"]
        for event in state.events
        if event["name"].endswith("_DOUBLE_CALL")
    ]
    prepared_before_call = all(any(marker < call for marker in prepared) for call in calls)
    restart_no_resign = True
    for event in state.events:
        if event["name"] != "WORKER_RESTARTED":
            continue
        durable = event["details"]["durable_attempt_state"]
        if durable in {"AMBIGUOUS_QUARANTINED", "CONSUMED", "SIGN_ATTEMPT_PREPARED"}:
            restart_no_resign = restart_no_resign and not any(
                call > event["sequence"] for call in calls
            )
    return prepared_before_call, restart_no_resign


def expected_injection_variant(case: dict[str, Any], repetition: int) -> str:
    case_id = case["case_id"]
    variants = {
        "M04": [
            "DROP_COMMIT_RESPONSE_AFTER_SERVER_COMMIT",
            "DROP_COMMIT_RESPONSE_WHILE_COMMIT_OUTCOME_IS_UNRESOLVED",
        ],
        "M07": [
            "COMPUTE_DATA_CRC32C_OVER_BASE64_TEXT",
            "RETURN_VERIFIED_DATA_CRC32C_FALSE",
        ],
        "M08": [
            "OMIT_CRYPTOKEYVERSION_SEGMENT",
            "SET_CRYPTOKEYVERSION_SEGMENT_TO_ZERO",
            "USE_PARENT_CRYPTOKEY_RESOURCE",
            "USE_NONCANONICAL_LEADING_ZERO_VERSION",
            "RETURN_DIFFERENT_CRYPTOKEYVERSION_NAME",
        ],
        "S09": [
            "RESTORE_OLDER_SNAPSHOT_WITHOUT_BUMP",
            "RETURN_STALE_REPLAYED_OR_FORKED_WITNESS_RECORD",
            "MAKE_INDEPENDENT_WITNESS_UNAVAILABLE_OR_CAS_CONFLICT",
        ],
        "S12": [
            "SEALED_ACTIVE_WITH_VALIDATED_STANDBY_TAKEOVER",
            "SEALED_ACTIVE_WITH_NO_VALIDATED_SUCCESSOR_RESPONSE",
        ],
        "S15": [
            "ROTATE_KEY_PINNED_VERSION_REMAINS_AVAILABLE",
            "ROTATE_KEY_PINNED_VERSION_UNAVAILABLE",
        ],
        "S17": [
            "MUTATE_SIGNATURE_VERSION_PREFIX",
            "MUTATE_PUBLIC_KEY_PIN",
            "MUTATE_MESSAGE",
        ],
    }
    if case_id in variants:
        values = variants[case_id]
        return values[(repetition - 1) % len(values)]
    return case["injection_cut"]


def execute_schedule_entry(
    contract: dict[str, Any],
    configuration: dict[str, Any],
    entry: ScheduleEntry,
) -> dict[str, Any]:
    validate_contract(contract)
    validate_configuration(configuration)
    index = _contract_index(contract)
    require((entry.track_id, entry.case_id) in index, "schedule case does not resolve")
    track, case = index[(entry.track_id, entry.case_id)]
    require(entry.configuration_sha256 == sha256_value(configuration), "entry configuration drift")
    state = SimulationState()
    pre_state = state.snapshot()
    expected_variant = expected_injection_variant(case, entry.repetition_index)
    state.event(
        "ASSIGNMENT_HASH_SEALED",
        assignment_sha256=entry.assignment_sha256,
        simulation_run_id=entry.run_id,
    )
    fault_controller = OneShotFaultController(
        assignment_sha256=entry.assignment_sha256,
        case_id=entry.case_id,
        injection_cut=case["injection_cut"],
        injection_variant=expected_variant,
        trigger_limit=0 if case["injection_cut"] == "NONE" else 1,
    )
    fault_controller.arm(state)
    fault_controller.start_candidate(state)
    if entry.track_id == MANAGED_TRACK:
        outcome = _managed_case(
            entry.case_id,
            entry.repetition_index,
            state,
            configuration,
            fault_controller,
        )
    else:
        outcome = _self_hosted_case(
            entry.case_id,
            entry.repetition_index,
            state,
            configuration,
            fault_controller,
        )
    if outcome.final_state is not None:
        require(outcome.final_state is not state, "restart reused the prior state object")
        state = outcome.final_state
    fault_controller.finish(state)
    require(outcome.injection_variant == expected_variant, "case variant schedule drift")
    require(outcome.classification in case["allowed_classifications"], "oracle classification outside frozen case set")
    require(state.simulated_application_calls <= 1, "one prepared attempt made multiple simulated calls")
    require(state.emitted_outputs == 0, "offline harness emitted output")
    require(state.attempt != "SIGN_ATTEMPT_PREPARED", "prepared attempt left unresolved")

    planned_locus = case["evidence_locus"]
    client_observation = planned_locus == "CLIENT_CONFORMANCE_DOUBLE"
    if client_observation:
        row_kind = "CLIENT_CONFORMANCE_OBSERVATION"
        evidence_class = "OFFLINE_CLIENT_CONFORMANCE_OBSERVATION_NOT_PROVIDER_OR_LAB_EVIDENCE"
        actual_origin = "OFFLINE_CLIENT_CONFORMANCE_DOUBLE"
        row_outcome = "OFFLINE_CLIENT_CONFORMANCE_COMPLETED"
        case_classification: str | None = outcome.classification
        simulated_classification: str | None = None
        classification_scope = "CLIENT_CONFORMANCE_DOUBLE_ONLY"
    else:
        row_kind = "MODEL_SCENARIO"
        evidence_class = "OFFLINE_MODEL_SCENARIO_ONLY_NOT_OBSERVATION"
        actual_origin = "OFFLINE_MODEL_SCENARIO"
        row_outcome = "OFFLINE_MODEL_SCENARIO_COMPLETED"
        case_classification = None
        simulated_classification = outcome.classification
        classification_scope = "MODEL_SCENARIO_ONLY"

    branch_invariants: list[str] = []
    if entry.case_id == "S12" and outcome.classification == "CONFORMING_OBSERVED":
        branch_invariants = ["S10", "S11", "S12"]
    explicit_invariants = list(case["invariant_ids"])
    effective_invariants = sorted(
        set(GLOBAL_INVARIANT_IDS) | set(explicit_invariants) | set(branch_invariants)
    )
    event_trace = list(state.events)
    trace_sha = sha256_value(event_trace)
    prepared_before_call, restart_no_resign = _event_order_assertions(state)
    post_state = state.snapshot()

    row = {
        "schema": RUN_ROW_SCHEMA,
        "harness_mode": HARNESS_MODE,
        "evidence_class": evidence_class,
        "row_kind": row_kind,
        "counts_toward_experiment": False,
        "counts_toward_harness_conformance": client_observation,
        "experimental_run_row": False,
        "contract_sha256": CONTRACT_SHA256,
        "schedule": entry.as_dict(),
        "case": {
            "family": case["family"],
            "planned_evidence_locus": planned_locus,
            "actual_evidence_origin": actual_origin,
            "injection_cut": case["injection_cut"],
            "injection_variant": outcome.injection_variant,
        },
        "row_outcome": row_outcome,
        "case_classification": case_classification,
        "simulated_classification": simulated_classification,
        "classification_scope": classification_scope,
        "oracle_classification_allowed": True,
        "explicit_invariant_ids": explicit_invariants,
        "branch_invariant_ids": branch_invariants,
        "effective_invariant_ids": effective_invariants,
        "state": post_state,
        "event_trace": event_trace,
        "evidence": {
            "provider_evidence_sha256": None,
            "simulator_trace_sha256": trace_sha,
            "pre_state_sha256": sha256_value(pre_state),
            "post_state_sha256": sha256_value(post_state),
            "request_sha256": outcome.request_sha256,
            "response_sha256": outcome.response_sha256,
            "message_sha256": MESSAGE_SHA256,
            "message_bytes": len(MESSAGE),
            "public_key_sha256": outcome.evidence_public_key_sha256,
            "test_signature_sha256": TEST_SIGNATURE_SHA256,
            "requested_key_version": outcome.requested_key_version,
            "validated_key_version": outcome.validated_key_version,
            "requested_isolation": outcome.requested_isolation,
            "effective_isolation": outcome.effective_isolation,
            "simulated_application_calls": state.simulated_application_calls,
            "simulated_processing_events": state.simulated_processing_events,
            "real_provider_calls": 0,
            "restarts": state.restarts,
            "emitted_outputs": state.emitted_outputs,
            "semantic_tokens": outcome.semantic_tokens,
        },
        "assertions": {
            "assignment_precedes_candidate_start": True,
            "injection_armed_prestart": True,
            "fresh_namespace": True,
            "exact_case_binding": True,
            "global_invariant_union_applied": set(GLOBAL_INVARIANT_IDS).issubset(effective_invariants),
            "classification_has_case_or_model_scope": True,
            "planned_and_actual_evidence_origins_separated": True,
            "provider_evidence_absent": True,
            "simulation_not_provider_evidence": True,
            "no_real_provider_io": True,
            "no_credentials": True,
            "no_paid_resources": True,
            "no_output_permit": True,
            "no_condition_output": True,
            "no_cross_track_certification": True,
            "terminal_ambiguity_closed": state.attempt != "SIGN_ATTEMPT_PREPARED",
            "prepared_before_simulated_sign": prepared_before_call,
            "single_consumption_attempt": state.simulated_application_calls <= 1,
            "restart_no_resign_from_consumed_or_ambiguous": restart_no_resign,
            "receipt_not_provider_processing_proof": True,
            "fault_controller_trigger_cardinality": sum(
                event["name"] == "ONE_SHOT_FAULT_TRIGGERED" for event in state.events
            ) == (0 if case["injection_cut"] == "NONE" else 1),
        },
        "boundary": BOUNDARY,
        "claim_ceiling": track["claim_ceiling"],
        "forbidden_claims": list(case["forbidden_claims"]),
        "retained": True,
    }
    validate_run_row(row, contract, configuration)
    return row


def _single_event(trace: list[dict[str, Any]], name: str) -> dict[str, Any]:
    matches = [event for event in trace if event["name"] == name]
    require(len(matches) == 1, f"event {name} cardinality drift")
    return matches[0]


def _event_before_after(
    trace: list[dict[str, Any]],
    trigger: dict[str, Any],
    before_name: str,
    after_name: str,
) -> None:
    before = _single_event(trace, before_name)
    after = _single_event(trace, after_name)
    require(
        before["sequence"] + 1 == trigger["sequence"]
        and trigger["sequence"] + 1 == after["sequence"],
        "fault trigger is not at its actual cut point",
    )


def _validate_fault_cut(trace: list[dict[str, Any]], row: dict[str, Any]) -> None:
    case_id = row["schedule"]["case_id"]
    variant = row["case"]["injection_variant"]
    triggers = [event for event in trace if event["name"] == "ONE_SHOT_FAULT_TRIGGERED"]
    if row["case"]["injection_cut"] == "NONE":
        require(not triggers, "control row triggered a fault")
        control = _single_event(trace, "CONTROL_NO_FAULT_TRIGGERED")
        require(control["details"] == {"case_id": case_id, "trigger_count": 0}, "control fault details drift")
        return
    require(len(triggers) == 1, "fault row trigger cardinality drift")
    trigger = triggers[0]
    require(
        trigger["details"]["case_id"] == case_id
        and trigger["details"]["injection_cut"] == row["case"]["injection_cut"]
        and trigger["details"]["injection_variant"] == variant
        and trigger["details"]["trigger_count"] == 1,
        "fault trigger binding drift",
    )
    if case_id == "M01":
        before = [
            event for event in trace
            if event["name"] == "SPANNER_SERIALIZABLE_TRANSACTION_ATTEMPT"
            and event["details"]["attempt"] == 1
        ]
        after = [
            event for event in trace
            if event["name"] == "SPANNER_DEFINITE_ABORT"
            and event["details"]["attempt"] == 1
        ]
        require(
            len(before) == len(after) == 1
            and before[0]["sequence"] + 1 == trigger["sequence"]
            and trigger["sequence"] + 1 == after[0]["sequence"],
            "M01 fault trigger cut drift",
        )
        return
    simple_bounds = {
        "M02": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "SPANNER_CLOSURE_SIDE_EFFECT_SENTINEL_REJECTED"),
        "M03": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "SPANNER_ISOLATION_PROFILE_REJECTED"),
        "M05": ("SPANNER_OUTBOX_COMMITTED", "KMS_REQUEST_REJECTED_BEFORE_ATTEMPT"),
        "M06": ("SPANNER_OUTBOX_COMMITTED", "KMS_REQUEST_REJECTED_BEFORE_ATTEMPT"),
        "M12": ("KMS_DOUBLE_PROCESSING_COMPLETED", "KMS_DOUBLE_RESPONSE_DROPPED"),
        "M13": ("KMS_RESPONSE_FULLY_VALIDATED", "SPANNER_RECEIPT_PERSIST_OUTCOME_UNKNOWN"),
        "M14": ("SPANNER_OUTBOX_COMMITTED", "TWO_WORKERS_RELEASED"),
        "M15": ("SPANNER_OUTBOX_COMMITTED", "WORKER_CRASHED_BEFORE_ATTEMPT_CAS"),
        "S01": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "ETCD_FOLLOWER_ISOLATED"),
        "S02": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "ETCD_SERIALIZABLE_READ_MODE_REJECTED"),
        "S03": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "ETCD_NESTED_TRANSACTION_REJECTED"),
        "S04": ("ETCD_REQUEST_ADMITTED_WITH_PENDING_COMMIT", "ETCD_LEADER_REMOVED_AFTER_REQUEST_ADMISSION"),
        "S05": ("ETCD_OUTBOX_COMMITTED", "ETCD_LEADER_LOST_POSTCOMMIT"),
        "S06": ("ETCD_OUTBOX_COMMITTED", "ETCD_TRANSACTION_ACK_DROPPED"),
        "S07": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "ETCD_QUORUM_LOST"),
        "S08": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "ETCD_WATCH_DELAYED"),
        "S09": ("RESTORE_WITNESS_CANDIDATE_STAGED", "EXTERNAL_WITNESS_VALIDATION_FAILED"),
        "S10": ("SNAPSHOT_HASH_VERIFIED", "RESTORE_IDENTITY_OR_WITNESS_BINDING_REJECTED"),
        "S11": ("SNAPSHOT_HASH_VERIFIED", "RESTORE_REVISION_BUMPED_AND_MARKED_COMPACTED"),
        "S12": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "OPENBAO_DIRECT_TARGET_SEAL_STATUS"),
        "S13": ("TRANSIT_DOUBLE_PROCESSING_COMPLETED", "TRANSIT_DOUBLE_RESPONSE_DROPPED"),
        "S14": ("TRANSIT_RESPONSE_FULLY_VALIDATED", "ETCD_RECEIPT_PERSIST_OUTCOME_UNKNOWN"),
        "S15": ("ETCD_OUTBOX_COMMITTED", "OPENBAO_KEY_ROTATED"),
        "S16": ("ETCD_OUTBOX_COMMITTED", "TRANSIT_ZERO_VERSION_REJECTED_BEFORE_ATTEMPT"),
    }
    if case_id in simple_bounds:
        _event_before_after(trace, trigger, *simple_bounds[case_id])
        return
    if case_id == "M04":
        before = (
            "SPANNER_SERVER_COMMIT_APPLIED"
            if variant == "DROP_COMMIT_RESPONSE_AFTER_SERVER_COMMIT"
            else "SPANNER_COMMIT_ADMITTED_OUTCOME_UNRESOLVED"
        )
        _event_before_after(trace, trigger, before, "SPANNER_COMMIT_RESPONSE_LOST")
        return
    if case_id in {"M07", "M08", "M09", "M10", "M11"}:
        precall = (
            case_id == "M07" and variant == "COMPUTE_DATA_CRC32C_OVER_BASE64_TEXT"
        ) or (case_id == "M08" and variant != "RETURN_DIFFERENT_CRYPTOKEYVERSION_NAME")
        if precall:
            before = "SPANNER_OUTBOX_COMMITTED"
            after = "KMS_SIGN_ATTEMPT_PREPARED" if case_id == "M07" else "KMS_RESOURCE_REJECTED_BEFORE_ATTEMPT"
            _event_before_after(trace, trigger, before, after)
        else:
            before = _single_event(trace, "KMS_SIGN_ATTEMPT_PREPARED")
            consumed = _single_event(trace, "KMS_SIGN_ATTEMPT_CALL_CONSUMED")
            call = _single_event(trace, "KMS_DOUBLE_CALL")
            require(
                before["sequence"] + 1 == trigger["sequence"]
                and trigger["sequence"] + 1 == consumed["sequence"]
                and consumed["sequence"] + 1 == call["sequence"],
                "managed response mutation cut drift",
            )
        return
    if case_id == "S17":
        if variant == "MUTATE_MESSAGE":
            _event_before_after(trace, trigger, "ETCD_OUTBOX_COMMITTED", "TRANSIT_SIGN_ATTEMPT_PREPARED")
        else:
            prepared = _single_event(trace, "TRANSIT_SIGN_ATTEMPT_PREPARED")
            consumed = _single_event(trace, "TRANSIT_SIGN_ATTEMPT_CALL_CONSUMED")
            call = _single_event(trace, "TRANSIT_DOUBLE_CALL")
            require(
                prepared["sequence"] + 1 == trigger["sequence"]
                and trigger["sequence"] + 1 == consumed["sequence"]
                and consumed["sequence"] + 1 == call["sequence"],
                "self-hosted response mutation cut drift",
            )
        return
    raise HarnessError(f"missing fault cut oracle for {case_id}")


def _expected_core_state(case_id: str, repetition: int) -> dict[str, Any]:
    if case_id.startswith("M"):
        if case_id in {"M02", "M03"}:
            return {
                "authority": "REJECTED_FAIL_CLOSED",
                "outbox": "NONE",
                "challenge_consumptions": 0,
                "logical_sink_reservations": 0,
                "database_attempts": 0,
            }
        if case_id == "M04" and repetition % 2 == 0:
            return {
                "authority": "FENCED_ABSENT",
                "outbox": "NONE",
                "challenge_consumptions": 0,
                "logical_sink_reservations": 0,
                "database_attempts": 1,
            }
        return {
            "authority": "AUTHORIZED_COMMITTED",
            "outbox": "SIGN_PENDING",
            "challenge_consumptions": 1,
            "logical_sink_reservations": 1,
            "database_attempts": 2 if case_id == "M01" else 1,
        }
    if case_id == "S01":
        return {
            "authority": "QUORUM_READ_OBSERVED" if repetition % 2 else "REJECTED_FAIL_CLOSED",
            "outbox": "NONE",
            "challenge_consumptions": 0,
            "logical_sink_reservations": 0,
            "database_attempts": 0,
        }
    if case_id in {"S02", "S03", "S07", "S08"}:
        return {
            "authority": "REJECTED_FAIL_CLOSED",
            "outbox": "NONE",
            "challenge_consumptions": 0,
            "logical_sink_reservations": 0,
            "database_attempts": 0,
        }
    if case_id in {"S09", "S10", "S11"}:
        return {
            "authority": "EMPTY",
            "outbox": "NONE",
            "challenge_consumptions": 0,
            "logical_sink_reservations": 0,
            "database_attempts": 0,
        }
    if case_id == "S04" and repetition % 2 == 0:
        return {
            "authority": "FENCED_ABSENT",
            "outbox": "NONE",
            "challenge_consumptions": 0,
            "logical_sink_reservations": 0,
            "database_attempts": 1,
        }
    if case_id == "S12" and repetition % 2 == 0:
        return {
            "authority": "REJECTED_FAIL_CLOSED",
            "outbox": "NONE",
            "challenge_consumptions": 0,
            "logical_sink_reservations": 0,
            "database_attempts": 0,
        }
    return {
        "authority": "AUTHORIZED_COMMITTED",
        "outbox": "SIGN_PENDING",
        "challenge_consumptions": 1,
        "logical_sink_reservations": 1,
        "database_attempts": 1,
    }


def _validate_durable_transition_replay(row: dict[str, Any]) -> None:
    trace = row["event_trace"]
    state = row["state"]
    schedule = row["schedule"]
    operation_id = schedule["simulation_run_id"]
    operation_key = _framed_hash(EXACT_KEY_DOMAIN, operation_id)
    transitions = [
        event for event in trace
        if "transition_record" in event["details"]
    ]
    rejected_envelopes = [
        event for event in trace
        if "transition_envelope" in event["details"]
        and "transition_record" not in event["details"]
    ]

    if rejected_envelopes:
        require(
            schedule["case_id"] == "S03"
            and len(rejected_envelopes) == 1
            and not transitions,
            "preexecution rejection envelope escaped S03",
        )
        rejected = rejected_envelopes[0]
        require(
            rejected["name"] == "ETCD_NESTED_TRANSACTION_REJECTED",
            "S03 rejection event drift",
        )
        envelope = rejected["details"]["transition_envelope"]
        exact_keys(envelope, set(TRANSITION_ENVELOPE_FIELDS), "transition envelope")
        require(
            envelope
            == {
                "phase": "NESTED_TRANSACTION_REJECTED_PREEXECUTION",
                "store_kind": "ETCD_LINEARIZABLE_TOP_LEVEL_EXACT_KEY_CAS",
                "operation_id": operation_id,
                "operation_key": operation_key,
                "consistency": "LINEARIZABLE",
                "nested": True,
                "leased": False,
                "compare_record_sha256": ZERO_SHA256,
                "observed_record_sha256": ZERO_SHA256,
                "expected_mod_revision": 0,
                "committed_record_sha256": ZERO_SHA256,
                "committed_revision": 0,
                "top_level_revision": 0,
                "mutation_count": 0,
                "cas_result": "REJECTED_PREEXECUTION",
                "response_revision_source": "NONE_PREEXECUTION_REJECTED",
            },
            "S03 preexecution rejection envelope drift",
        )
        require(
            state["durable_operation_record_sha256"] == ZERO_SHA256
            and state["durable_operation_revision"] == 0,
            "S03 rejection mutated durable operation state",
        )

    if not transitions:
        require(
            state["durable_operation_record_sha256"] == ZERO_SHA256
            and state["durable_operation_revision"] == 0,
            "row without transition retained durable operation state",
        )
        return

    require(not rejected_envelopes, "applied and preexecution-rejected transitions mixed")
    if schedule["case_id"] in {"M04", "S04"}:
        expected_exact_phase = (
            "AUTHORITY_OUTBOX_COMMITTED"
            if schedule["repetition_index"] % 2
            else "TERMINAL_FENCE_COMMITTED"
        )
        require(
            len(transitions) == 1
            and transitions[0]["details"]["transition_envelope"]["phase"]
            == expected_exact_phase,
            "unknown-outcome exact commit phase/parity drift",
        )
    previous_record: dict[str, Any] | None = None
    previous_sha256 = ZERO_SHA256
    previous_revision = 0
    track_is_managed = schedule["track_id"] == MANAGED_TRACK
    expected_phases = {
        None: {"AUTHORITY_OUTBOX_COMMITTED", "TERMINAL_FENCE_COMMITTED"},
        "AUTHORITY_OUTBOX_COMMITTED": {
            "SIGN_ATTEMPT_PREPARED", "PRE_ATTEMPT_REJECTED_FAIL_CLOSED",
        },
        "SIGN_ATTEMPT_PREPARED": {"SIGN_ATTEMPT_CALL_CONSUMED"},
        "SIGN_ATTEMPT_CALL_CONSUMED": {
            "SIGNATURE_RECEIPT_COMMITTED", "AMBIGUOUS_QUARANTINED",
            "RESPONSE_REJECTED_FAIL_CLOSED",
        },
    }
    previous_phase: str | None = None

    for index, event in enumerate(transitions, start=1):
        details = event["details"]
        record = details["transition_record"]
        record_sha256 = details["transition_record_sha256"]
        envelope = details["transition_envelope"]
        exact_keys(record, set(OPERATION_STATE_RECORD_FIELDS), "operation state record")
        exact_keys(envelope, set(TRANSITION_ENVELOPE_FIELDS), "transition envelope")
        require(sha256_value(record) == record_sha256, "transition record hash drift")
        require(
            envelope["phase"] in expected_phases.get(previous_phase, set()),
            "illegal durable operation phase transition",
        )
        phase = envelope["phase"]
        require(
            envelope["operation_id"] == record["operation_id"] == operation_id
            and envelope["operation_key"] == operation_key,
            "transition operation binding drift",
        )
        require(
            envelope["compare_record_sha256"] == previous_sha256
            and envelope["observed_record_sha256"] == previous_sha256
            and envelope["expected_mod_revision"] == previous_revision
            and envelope["committed_record_sha256"] == record_sha256
            and envelope["committed_revision"] == previous_revision + 1
            and envelope["top_level_revision"] == previous_revision + 1
            and envelope["mutation_count"] == 1
            and envelope["cas_result"] == "APPLIED"
            and envelope["nested"] is False
            and envelope["leased"] is False,
            "transition exact-CAS envelope drift",
        )
        if track_is_managed:
            require(
                envelope["store_kind"] == "SPANNER_SERIALIZABLE_EXACT_KEY_CAS"
                and envelope["consistency"] == "SERIALIZABLE"
                and envelope["response_revision_source"]
                == "SERIALIZABLE_COMMIT_MODEL",
                "managed transition store semantics drift",
            )
        else:
            require(
                envelope["store_kind"]
                == "ETCD_LINEARIZABLE_TOP_LEVEL_EXACT_KEY_CAS"
                and envelope["consistency"] == "LINEARIZABLE"
                and envelope["response_revision_source"]
                == "TOP_LEVEL_TXN_HEADER",
                "self-hosted transition store semantics drift",
            )
        require(
            record["record_kind"]
            in {"EXACT_OPERATION_RECORD", "TERMINAL_FENCE"}
            and record["message_sha256"] == MESSAGE_SHA256
            and record["public_key_pin_sha256"] == PUBLIC_KEY_SHA256
            and type(record["exact_key_version"]) is int
            and record["exact_key_version"] > 0,
            "transition frozen signing binding drift",
        )
        if phase == "TERMINAL_FENCE_COMMITTED":
            require(
                record["record_kind"] == "TERMINAL_FENCE"
                and record["authority"] == "FENCED_ABSENT"
                and record["outbox"] == "NONE"
                and record["challenge_consumptions"] == 0
                and record["logical_sink_reservations"] == 0,
                "terminal fence transition atomic binding drift",
            )
        else:
            require(
                record["record_kind"] == "EXACT_OPERATION_RECORD"
                and record["authority"] == "AUTHORIZED_COMMITTED"
                and record["outbox"] == "SIGN_PENDING"
                and record["challenge_consumptions"] == 1
                and record["logical_sink_reservations"] == 1,
                "transition authority/outbox atomic binding drift",
            )
        if previous_record is not None:
            for field_name in (
                "operation_id", "authority", "outbox", "challenge_consumptions",
                "logical_sink_reservations", "message_sha256",
                "exact_key_version", "public_key_pin_sha256",
            ):
                require(
                    record[field_name] == previous_record[field_name],
                    f"transition immutable field drift: {field_name}",
                )

        zero_tail = {
            "prepared_record_sha256": ZERO_SHA256,
            "call_binding_sha256": ZERO_SHA256,
            "processed_response_sha256": ZERO_SHA256,
            "validated_response_sha256": ZERO_SHA256,
            "validation_binding_sha256": ZERO_SHA256,
            "receipt_binding_sha256": ZERO_SHA256,
            "receipt": "NONE",
        }
        if phase == "AUTHORITY_OUTBOX_COMMITTED":
            expected_event_name = (
                "SPANNER_SERVER_COMMIT_APPLIED"
                if schedule["case_id"] == "M04"
                else "ETCD_DELAYED_COMMIT_APPLIED_AFTER_ELECTION"
                if schedule["case_id"] == "S04"
                else "SPANNER_OUTBOX_COMMITTED"
                if track_is_managed
                else "ETCD_TOP_LEVEL_CAS"
            )
            require(
                event["name"] == expected_event_name
                and record["attempt"] == "NONE"
                and record["attempt_consumed"] is False
                and record["terminal"] is False
                and all(record[key] == value for key, value in zero_tail.items()),
                "authority/outbox transition record drift",
            )
            if event["name"] == "SPANNER_SERVER_COMMIT_APPLIED":
                require(
                    details["operation_key"] == envelope["operation_key"]
                    and details["record_sha256"] == record_sha256
                    and details["revision"] == envelope["committed_revision"],
                    "managed exact commit outer/transition binding drift",
                )
            elif event["name"] == "ETCD_DELAYED_COMMIT_APPLIED_AFTER_ELECTION":
                require(
                    details["operation_key"] == envelope["operation_key"]
                    and details["record_sha256"] == record_sha256
                    and details["cas_result"] == envelope["cas_result"]
                    and details["revision"] == envelope["committed_revision"],
                    "self-hosted exact commit outer/transition binding drift",
                )
        elif phase == "TERMINAL_FENCE_COMMITTED":
            require(
                schedule["case_id"] in {"M04", "S04"}
                and schedule["repetition_index"] % 2 == 0
                and
                event["name"]
                == (
                    "SPANNER_ABSENT_TO_TERMINAL_FENCE_TRANSACTION"
                    if track_is_managed
                    else "ETCD_SAME_KEY_ABSENT_TO_TERMINAL_FENCE_CAS"
                )
                and record["attempt"] == "NONE"
                and record["attempt_consumed"] is False
                and record["receipt"] == "NONE"
                and record["prepared_record_sha256"] == ZERO_SHA256
                and record["call_binding_sha256"] == ZERO_SHA256
                and record["processed_response_sha256"] == ZERO_SHA256
                and record["validated_response_sha256"] == ZERO_SHA256
                and record["validation_binding_sha256"] == ZERO_SHA256
                and record["receipt_binding_sha256"] == ZERO_SHA256
                and record["terminal"] is True,
                "terminal fence transition record drift",
            )
            require(
                details["operation_key"] == envelope["operation_key"]
                and details["consistency"]
                == ("SERIALIZABLE" if track_is_managed else "LINEARIZABLE_TOP_LEVEL_CAS")
                and details["compare_record_sha256"]
                == envelope["compare_record_sha256"]
                and details["committed_record_sha256"] == record_sha256
                and details["cas_result"] == envelope["cas_result"]
                and details["revision"] == envelope["committed_revision"],
                "terminal fence outer/transition binding drift",
            )
        elif phase == "SIGN_ATTEMPT_PREPARED":
            require(
                event["name"].endswith("_SIGN_ATTEMPT_PREPARED")
                and record["attempt"] == "SIGN_ATTEMPT_PREPARED"
                and record["attempt_consumed"] is False
                and record["prepared_record_sha256"] != ZERO_SHA256
                and all(
                    record[key] == value
                    for key, value in zero_tail.items()
                    if key != "prepared_record_sha256"
                )
                and record["terminal"] is False,
                "prepared transition record drift",
            )
        elif phase == "SIGN_ATTEMPT_CALL_CONSUMED":
            require(
                event["name"].endswith("_SIGN_ATTEMPT_CALL_CONSUMED")
                and record["attempt"] == "SIGN_ATTEMPT_PREPARED"
                and record["attempt_consumed"] is True
                and record["prepared_record_sha256"] != ZERO_SHA256
                and record["call_binding_sha256"] != ZERO_SHA256
                and record["processed_response_sha256"] == ZERO_SHA256
                and record["validated_response_sha256"] == ZERO_SHA256
                and record["validation_binding_sha256"] == ZERO_SHA256
                and record["receipt"] == "NONE"
                and record["receipt_binding_sha256"] == ZERO_SHA256
                and record["terminal"] is False,
                "call-consumption transition record drift",
            )
        elif phase == "SIGNATURE_RECEIPT_COMMITTED":
            require(
                event["name"].endswith("_SIGNATURE_RECEIPT_COMMITTED")
                and record["attempt"] == "CONSUMED"
                and record["attempt_consumed"] is True
                and record["processed_response_sha256"]
                == record["validated_response_sha256"] != ZERO_SHA256
                and record["validation_binding_sha256"] != ZERO_SHA256
                and record["receipt"] == "SIGNATURE_RECEIPT_COMMITTED"
                and record["receipt_binding_sha256"] != ZERO_SHA256
                and record["terminal"] is True,
                "receipt transition record drift",
            )
        elif phase == "AMBIGUOUS_QUARANTINED":
            require(
                event["name"].endswith("_AMBIGUOUS_QUARANTINED")
                and record["attempt"] == "AMBIGUOUS_QUARANTINED"
                and record["attempt_consumed"] is True
                and record["processed_response_sha256"] != ZERO_SHA256
                and record["receipt"] == "NONE"
                and record["receipt_binding_sha256"] == ZERO_SHA256
                and record["terminal"] is True,
                "quarantine transition record drift",
            )
            require(
                (
                    record["validation_binding_sha256"] == ZERO_SHA256
                    and record["validated_response_sha256"] == ZERO_SHA256
                )
                or (
                    record["validation_binding_sha256"] != ZERO_SHA256
                    and record["validated_response_sha256"]
                    == record["processed_response_sha256"]
                ),
                "quarantine validation state drift",
            )
        elif phase == "RESPONSE_REJECTED_FAIL_CLOSED":
            require(
                event["name"].endswith("_RESPONSE_REJECTED")
                and record["attempt"] == "REJECTED_FAIL_CLOSED"
                and record["attempt_consumed"] is True
                and record["processed_response_sha256"] != ZERO_SHA256
                and record["validated_response_sha256"] == ZERO_SHA256
                and record["validation_binding_sha256"] == ZERO_SHA256
                and record["receipt"] == "NONE"
                and record["receipt_binding_sha256"] == ZERO_SHA256
                and record["terminal"] is True,
                "response-rejection transition record drift",
            )
        elif phase == "PRE_ATTEMPT_REJECTED_FAIL_CLOSED":
            require(
                record["attempt"] == "REJECTED_FAIL_CLOSED"
                and record["attempt_consumed"] is False
                and record["terminal"] is True
                and all(record[key] == value for key, value in zero_tail.items()),
                "pre-attempt rejection transition record drift",
            )

        previous_record = record
        previous_sha256 = record_sha256
        previous_revision = index
        previous_phase = phase

    final_record = previous_record
    require(final_record is not None, "transition replay lost final record")
    require(
        state["durable_operation_record_sha256"] == previous_sha256
        and state["durable_operation_revision"] == previous_revision,
        "durable operation state/tip drift",
    )
    projection = {
        "authority": "authority",
        "outbox": "outbox",
        "attempt": "attempt",
        "attempt_consumed": "attempt_consumed",
        "receipt": "receipt",
        "challenge_consumptions": "challenge_consumptions",
        "logical_sink_reservations": "logical_sink_reservations",
        "prepared_record_sha256": "prepared_record_sha256",
        "call_binding_sha256": "call_binding_sha256",
        "processed_response_sha256": "processed_response_sha256",
        "validated_response_sha256": "validated_response_sha256",
        "validation_binding_sha256": "validation_binding_sha256",
        "receipt_binding_sha256": "receipt_binding_sha256",
    }
    require(
        all(state[state_key] == final_record[record_key] for state_key, record_key in projection.items()),
        "durable operation record/state projection drift",
    )
    if schedule["case_id"] == "M05":
        first = transitions[0]
        attempts = [
            event for event in trace
            if event["name"] == "SPANNER_SERIALIZABLE_TRANSACTION_ATTEMPT"
        ]
        require(
            first["name"] == "SPANNER_OUTBOX_COMMITTED"
            and len(attempts) == 1
            and attempts[0]["sequence"] + 1 == first["sequence"],
            "M05 authority/challenge/sink/message/key/outbox not bound to one transaction",
        )


def _validate_event_trace(row: dict[str, Any]) -> None:
    trace = row["event_trace"]
    schedule = row["schedule"]
    forbidden_claim_tokens = (
        "PROVIDER_PROCESSING_OBSERVED",
        "PROVIDER_EVIDENCE_PRESENT",
        "PRODUCTION_READY",
        "OUTPUT_PERMIT_GRANTED",
        "EXACTLY_ONCE_PROVEN",
        "REAL_PROVIDER_CALL",
    )
    for event in trace:
        exact_keys(event, {"sequence", "name", "details"}, "event")
        name = event["name"]
        require(name in EVENT_DETAIL_KEYS, f"unknown event name {name}")
        exact_keys(event["details"], set(EVENT_DETAIL_KEYS[name]), f"{name} details")
        encoded_details = json.dumps(event["details"], sort_keys=True).upper()
        require(
            not any(token in encoded_details for token in forbidden_claim_tokens),
            f"event {name} contains a forbidden provenance claim",
        )

    spanner_attempts = [
        event for event in trace
        if event["name"] == "SPANNER_SERIALIZABLE_TRANSACTION_ATTEMPT"
    ]
    require(
        [event["details"]["attempt"] for event in spanner_attempts]
        == list(range(1, len(spanner_attempts) + 1))
        and all(
            event["details"]["closure_scope"] == "DATABASE_ONLY"
            for event in spanner_attempts
        ),
        "Spanner transaction-attempt evidence drift",
    )
    for event in [event for event in trace if event["name"] == "SPANNER_OUTBOX_COMMITTED"]:
        require(event["details"]["outbox"] == "SIGN_PENDING", "Spanner outbox event drift")
    for event in [event for event in trace if event["name"] == "ETCD_TOP_LEVEL_CAS"]:
        require(
            all(
                event["details"][field_name] == expected
                for field_name, expected in {
                    "serializable": False,
                    "nested": False,
                    "leased": False,
                    "response_revision_source": "TOP_LEVEL_HEADER",
                }.items()
            ),
            "etcd top-level CAS event drift",
        )
    for event in [event for event in trace if event["name"] == "ETCD_OUTBOX_COMMITTED"]:
        require(event["details"] == {"outbox": "SIGN_PENDING"}, "etcd outbox event drift")

    _validate_durable_transition_replay(row)

    assignment = _single_event(trace, "ASSIGNMENT_HASH_SEALED")
    arm = _single_event(trace, "ONE_SHOT_FAULT_CONTROLLER_ARMED")
    start = _single_event(trace, "CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM")
    require(
        assignment["sequence"] == 1
        and arm["sequence"] == 2
        and start["sequence"] == 3,
        "assignment/arm/start order drift",
    )
    require(
        assignment["details"]
        == {
            "assignment_sha256": schedule["assignment_sha256"],
            "simulation_run_id": schedule["simulation_run_id"],
        },
        "assignment event binding drift",
    )
    require(
        arm["details"]["assignment_sha256"] == schedule["assignment_sha256"]
        and arm["details"]["case_id"] == schedule["case_id"]
        and arm["details"]["injection_cut"] == row["case"]["injection_cut"]
        and arm["details"]["injection_variant"] == row["case"]["injection_variant"],
        "fault arm binding drift",
    )
    _validate_fault_cut(trace, row)

    prepared_events = [event for event in trace if event["name"].endswith("_SIGN_ATTEMPT_PREPARED")]
    consumption_events = [
        event for event in trace
        if event["name"].endswith("_SIGN_ATTEMPT_CALL_CONSUMED")
    ]
    call_events = [event for event in trace if event["name"].endswith("_DOUBLE_CALL")]
    processing_events = [event for event in trace if event["name"].endswith("_DOUBLE_PROCESSING_COMPLETED")]
    delivery_events = [
        event for event in trace
        if event["name"].endswith("_DOUBLE_RESPONSE_OBSERVED")
        or event["name"].endswith("_DOUBLE_RESPONSE_DROPPED")
    ]
    validation_events = [event for event in trace if event["name"].endswith("_RESPONSE_FULLY_VALIDATED")]
    receipt_events = [event for event in trace if event["name"].endswith("_SIGNATURE_RECEIPT_COMMITTED")]
    rejection_events = [event for event in trace if event["name"].endswith("_RESPONSE_REJECTED")]
    require(len(prepared_events) <= 1 and len(call_events) <= 1, "prepared/call cardinality drift")
    require(len(consumption_events) == len(call_events), "call-consumption CAS cardinality drift")
    require(len(call_events) == len(processing_events), "call/processing cardinality drift")
    require(len(call_events) == len(delivery_events), "call/response-delivery cardinality drift")
    require(row["state"]["attempt_consumed"] is bool(call_events), "attempt consumption state drift")
    require(row["state"]["simulated_application_calls"] == len(call_events), "state call counter drift")
    require(row["state"]["simulated_processing_events"] == len(processing_events), "state processing counter drift")
    if prepared_events:
        prepared = prepared_events[0]
        record = prepared["details"]["prepared_record"]
        exact_keys(record, set(PreparedAttemptRecord.__dataclass_fields__), "prepared record")
        require(prepared["details"]["durable"] is True, "prepared record is not durable")
        require(record["operation_id"] == schedule["simulation_run_id"], "prepared operation id drift")
        require(record["message_sha256"] == MESSAGE_SHA256, "prepared message drift")
        require(record["public_key_pin_sha256"] == PUBLIC_KEY_SHA256, "prepared public key drift")
        require(record["attempt_sequence"] == 1 and record["exact_key_version"] > 0, "prepared sequence/version drift")
        require(sha256_value(record) == prepared["details"]["prepared_record_sha256"], "prepared record hash drift")
        require(
            all(
                row["state"][field_name] == expected
                for field_name, expected in {
                    "prepared_operation_id": record["operation_id"],
                    "prepared_request_sha256": record["canonical_request_sha256"],
                    "prepared_key_version": record["exact_key_version"],
                    "prepared_public_key_sha256": record["public_key_pin_sha256"],
                    "prepared_message_sha256": record["message_sha256"],
                    "prepared_attempt_sequence": record["attempt_sequence"],
                    "prepared_record_sha256": prepared["details"]["prepared_record_sha256"],
                }.items()
            ),
            "prepared durable state drift",
        )
    if call_events:
        require(prepared_events and prepared_events[0]["sequence"] < call_events[0]["sequence"], "call preceded prepared record")
        call = call_events[0]
        consumption = consumption_events[0]
        details = call["details"]
        require(
            prepared_events[0]["sequence"] < consumption["sequence"]
            and consumption["sequence"] + 1 == call["sequence"],
            "call was not immediately preceded by durable attempt consumption",
        )
        require(
            consumption["details"]["transition_record"]["call_binding_sha256"]
            == details["call_binding_sha256"]
            and consumption["details"]["transition_record"]["attempt_consumed"]
            is True,
            "call/consumption transition binding drift",
        )
        require(details["hidden_retries"] is False and details["evidence_class"] == EVIDENCE_CLASS, "double call provenance drift")
        require(
            details["operation_id"] == schedule["simulation_run_id"]
            == row["state"]["prepared_operation_id"]
            and details["prepared_record_sha256"] == row["state"]["prepared_record_sha256"]
            and details["key_version"] == row["state"]["prepared_key_version"]
            and details["public_key_sha256"] == row["state"]["prepared_public_key_sha256"]
            and details["message_sha256"] == row["state"]["prepared_message_sha256"]
            and details["attempt_sequence"] == row["state"]["prepared_attempt_sequence"] == 1,
            "double call/prepared binding drift",
        )
        expected_call_binding = _framed_hash(
            "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/double-call",
            details["prepared_record_sha256"],
            details["request_sha256"],
            details["execution_request_id"] or "NOT_APPLICABLE",
            details["executing_node"] or "NOT_APPLICABLE",
            details["execution_cluster_id"] or "NOT_APPLICABLE",
            details["audit_record_sha256"] or "NOT_APPLICABLE",
            details["wire_attempt_sha256"] or "NOT_APPLICABLE",
        )
        require(details["call_binding_sha256"] == expected_call_binding, "call binding hash drift")
        require(details["request_sha256"] == row["state"]["prepared_request_sha256"], "call request/prepared mismatch")
        require(details["call_binding_sha256"] == row["state"]["call_binding_sha256"], "call state binding drift")
        processing = processing_events[0]
        delivery = delivery_events[0]
        require(call["sequence"] < processing["sequence"] < delivery["sequence"], "call/processing/delivery order drift")
        require(processing["details"]["call_binding_sha256"] == expected_call_binding, "processing call binding drift")
        require(processing["details"]["response_sha256"] == row["state"]["processed_response_sha256"], "processed response state drift")
        require(
            delivery["details"]["call_binding_sha256"] == expected_call_binding
            and delivery["details"]["response_sha256"]
            == processing["details"]["response_sha256"],
            "response delivery binding drift",
        )
    else:
        require(
            row["state"]["call_binding_sha256"] == ZERO_SHA256
            and row["state"]["processed_response_sha256"] == ZERO_SHA256,
            "zero-call row retained a call binding",
        )
    if validation_events:
        require(call_events and len(validation_events) == 1, "validation cardinality drift")
        details = validation_events[0]["details"]
        call_details = call_events[0]["details"]
        require(
            details["operation_id"] == row["state"]["prepared_operation_id"]
            and details["call_binding_sha256"] == call_details["call_binding_sha256"]
            and details["request_sha256"] == row["state"]["prepared_request_sha256"]
            and details["key_version"] == row["state"]["prepared_key_version"]
            and details["public_key_sha256"] == row["state"]["prepared_public_key_sha256"]
            and details["message_sha256"] == row["state"]["prepared_message_sha256"]
            and all(
                details[field_name] == call_details[field_name]
                for field_name in (
                    "execution_request_id",
                    "executing_node",
                    "execution_cluster_id",
                    "audit_record_sha256",
                    "wire_attempt_sha256",
                )
            ),
            "validation/prepared call binding drift",
        )
        require(details["response_sha256"] == row["state"]["processed_response_sha256"], "validation response mismatch")
        require(
            delivery_events[0]["name"].endswith("_DOUBLE_RESPONSE_OBSERVED")
            and delivery_events[0]["sequence"] < validation_events[0]["sequence"],
            "validation preceded observed response",
        )
        expected_validation = _framed_hash(
            "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/response-validation",
            details["call_binding_sha256"], details["response_sha256"], details["request_sha256"],
            str(details["key_version"]), details["public_key_sha256"], details["message_sha256"],
            details["execution_request_id"] or "NOT_APPLICABLE",
            details["executing_node"] or "NOT_APPLICABLE",
            details["execution_cluster_id"] or "NOT_APPLICABLE",
            details["audit_record_sha256"] or "NOT_APPLICABLE",
            details["wire_attempt_sha256"] or "NOT_APPLICABLE",
        )
        require(details["validation_binding_sha256"] == expected_validation, "validation binding drift")
        require(details["message_bytes"] == 137, "validated message length drift")
        require(row["state"]["validation_binding_sha256"] == expected_validation, "validation state binding drift")
        require(row["state"]["validated_response_sha256"] == details["response_sha256"], "validated response state drift")
    else:
        require(
            row["state"]["validation_binding_sha256"] == ZERO_SHA256
            and row["state"]["validated_response_sha256"] == ZERO_SHA256,
            "unvalidated row retained validation evidence",
        )
    for rejection in rejection_events:
        require(
            len(delivery_events) == 1
            and delivery_events[0]["name"].endswith("_DOUBLE_RESPONSE_OBSERVED")
            and delivery_events[0]["sequence"] < rejection["sequence"],
            "response rejection preceded observed response",
        )
    if receipt_events:
        require(call_events and validation_events and len(receipt_events) == 1, "receipt causal chain missing")
        details = receipt_events[0]["details"]
        call_details = call_events[0]["details"]
        validation_details = validation_events[0]["details"]
        require(
            details["operation_id"] == row["state"]["prepared_operation_id"]
            and details["prepared_record_sha256"] == row["state"]["prepared_record_sha256"]
            and details["request_sha256"] == row["state"]["prepared_request_sha256"]
            and details["response_sha256"] == row["state"]["validated_response_sha256"]
            and details["key_version"] == row["state"]["prepared_key_version"]
            and details["public_key_sha256"] == row["state"]["prepared_public_key_sha256"]
            and details["message_sha256"] == row["state"]["prepared_message_sha256"]
            and details["call_binding_sha256"] == call_details["call_binding_sha256"]
            and details["validation_binding_sha256"]
            == validation_details["validation_binding_sha256"]
            and all(
                details[field_name] == call_details[field_name]
                == validation_details[field_name]
                for field_name in (
                    "execution_request_id",
                    "executing_node",
                    "execution_cluster_id",
                    "audit_record_sha256",
                    "wire_attempt_sha256",
                )
            ),
            "receipt upstream binding drift",
        )
        expected_receipt = _framed_hash(
            "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/durable-receipt",
            details["prepared_record_sha256"], details["call_binding_sha256"],
            details["validation_binding_sha256"], details["response_sha256"],
            details["execution_request_id"] or "NOT_APPLICABLE",
            details["executing_node"] or "NOT_APPLICABLE",
            details["execution_cluster_id"] or "NOT_APPLICABLE",
            details["audit_record_sha256"] or "NOT_APPLICABLE",
            details["wire_attempt_sha256"] or "NOT_APPLICABLE",
        )
        require(details["receipt_binding_sha256"] == expected_receipt, "receipt binding drift")
        require(row["state"]["receipt_binding_sha256"] == expected_receipt, "receipt state binding drift")
        require(receipt_events[0]["sequence"] > validation_events[0]["sequence"], "receipt preceded validation")
    else:
        require(row["state"]["receipt_binding_sha256"] == ZERO_SHA256, "row claims an untraced receipt")

    for durable in [event for event in trace if event["name"] == "DURABLE_IMAGE_SERIALIZED"]:
        image = durable["details"]["durable_image"]
        exact_keys(image, STATE_FIELDS, "durable image")
        require(sha256_value(image) == durable["details"]["image_sha256"], "durable image hash drift")
        destroyed = _single_event(trace, "EPHEMERAL_WORKER_DESTROYED")
        restarted = _single_event(trace, "WORKER_RESTARTED")
        constructed = _single_event(trace, "NEW_WORKER_CONSTRUCTED_FROM_DURABLE_IMAGE")
        no_resign = _single_event(trace, "RESTART_NO_RESIGN_CONFIRMED")
        require(
            durable["sequence"] < destroyed["sequence"] < restarted["sequence"]
            < constructed["sequence"] < no_resign["sequence"],
            "restart transition order drift",
        )
        require(
            restarted["details"]
            == {
                "calls_before_restart": image["simulated_application_calls"],
                "durable_attempt_state": image["attempt"],
            }
            and no_resign["details"]["calls_after_restart"]
            == image["simulated_application_calls"],
            "restart durable image binding drift",
        )
        if schedule["case_id"] != "M15":
            expected_after_restart = dict(image)
            expected_after_restart["restarts"] += 1
            require(expected_after_restart == row["state"], "post-restart state differs from durable image")
        else:
            expected_durable_image = SimulationState().snapshot()
            expected_authority_record = _operation_state_record(
                schedule["simulation_run_id"],
                7,
                authority="AUTHORIZED_COMMITTED",
                outbox="SIGN_PENDING",
                challenge_consumptions=1,
                logical_sink_reservations=1,
            )
            expected_durable_image.update(
                authority="AUTHORIZED_COMMITTED",
                outbox="SIGN_PENDING",
                database_attempts=1,
                challenge_consumptions=1,
                logical_sink_reservations=1,
                durable_operation_record_sha256=sha256_value(
                    expected_authority_record
                ),
                durable_operation_revision=1,
            )
            require(
                image == expected_durable_image,
                "M15 crash-before-attempt durable image drift",
            )
            post_restart_signing_fields = {
                "attempt",
                "attempt_consumed",
                "call_binding_sha256",
                "durable_operation_record_sha256",
                "durable_operation_revision",
                "prepared_attempt_sequence",
                "prepared_key_version",
                "prepared_message_sha256",
                "prepared_operation_id",
                "prepared_public_key_sha256",
                "prepared_record_sha256",
                "prepared_request_sha256",
                "processed_response_sha256",
                "receipt",
                "receipt_binding_sha256",
                "simulated_application_calls",
                "simulated_processing_events",
                "validated_response_sha256",
                "validation_binding_sha256",
            }
            require(
                row["state"]["restarts"] == image["restarts"] + 1
                and all(
                    row["state"][field_name] == image[field_name]
                    for field_name in STATE_FIELDS
                    - post_restart_signing_fields
                    - {"restarts"}
                ),
                "M15 durable image changed outside post-restart signing fields",
            )
    for worker in [event for event in trace if event["name"] == "NEW_WORKER_CONSTRUCTED_FROM_DURABLE_IMAGE"]:
        require(
            worker["details"]
            == {"prior_worker_ephemeral_state_reused": False, "state_object_reused": False},
            "restart reused ephemeral worker state",
        )

    witness_events = [
        event for event in trace if event["name"] in {
            "EXTERNAL_WITNESS_EXACT_CAS_COMMITTED",
            "EXTERNAL_WITNESS_VALIDATION_FAILED",
            "RESTORE_IDENTITY_OR_WITNESS_BINDING_REJECTED",
        }
    ]
    for event in witness_events:
        details = event["details"]
        record = details["witness_record"]
        exact_keys(record, WITNESS_FIELDS, "external witness record")
        require(sha256_value(record) == details["witness_record_sha256"], "witness record hash drift")
        require(details["actor_domain"] == WITNESS_ACTOR_DOMAIN, "witness ledger domain drift")
        require(details["caller_actor_domain"] == WITNESS_ACTOR_DOMAIN, "witness caller domain drift")
        expected_lineage = f"logical-lineage-{schedule['simulation_run_id'][:24]}"
        require(
            details["logical_cluster_lineage_id"] == expected_lineage
            and details["witness_key"]
            == _framed_hash(
                f"{WITNESS_DOMAIN}/exact-key",
                record["authority_id"],
                expected_lineage,
            ),
            "witness exact key/lineage drift",
        )
        require(record["domain"] == WITNESS_DOMAIN, "witness record domain drift")
        opened = _single_event(trace, "EXTERNAL_WITNESS_LEDGER_OPENED")["details"]
        require(
            opened["read_consistency"] == "LINEARIZABLE"
            and opened["read_revision"] == opened["generation"]
            and opened["observed_record_sha256"] == opened["current_record_sha256"]
            and opened["observed_generation"] == opened["generation"]
            and opened["witness_key"] == details["witness_key"]
            and
            details["expected_previous_record_sha256"]
            == record["previous_record_sha256"]
            and details["expected_generation"] == max(record["generation"] - 1, 0)
            and details["observed_previous_record_sha256"]
            == opened["current_record_sha256"]
            and details["observed_generation"] == opened["generation"]
            and details["observed_witness_key"] == details["witness_key"],
            "witness CAS compare envelope drift",
        )
        if details["cas_result"] == "APPLIED":
            require(record["new_cluster_id"] != record["prior_cluster_id"], "witness cluster id reused")
            require(record["new_incarnation_id"] != record["prior_incarnation_id"], "witness incarnation id reused")
            require(record["mark_compacted"] is True and record["bump_revision"] > 0, "applied witness lacks bump/compact")
            require(record["new_revision_floor"] == record["snapshot_revision"] + record["bump_revision"], "applied witness revision drift")
            require(record["previous_record_sha256"] == details["observed_previous_record_sha256"], "witness previous hash compare drift")
            require(record["generation"] == details["observed_generation"] + 1, "witness generation compare drift")
            require(details["rejection_reason"] == "NONE", "applied witness has rejection reason")
            require(row["state"]["witness_record_sha256"] == details["witness_record_sha256"], "witness trace/state hash drift")
            require(row["state"]["witness_generation"] == record["generation"], "witness trace/state generation drift")
        else:
            require(details["cas_result"] == "REJECTED_NO_MUTATION" and details["rejection_reason"] != "NONE", "failed witness CAS drift")

    case_id = schedule["case_id"]
    expected_exact_key_version = 7 if case_id.startswith("M") else 2
    expected_operation_key = _framed_hash(EXACT_KEY_DOMAIN, schedule["simulation_run_id"])
    if case_id in {"M04", "S04"}:
        suffix = "SPANNER" if case_id == "M04" else "ETCD"
        bare_name = f"{suffix}_BARE_ABSENT_{'STRONG' if case_id == 'M04' else 'LINEARIZABLE'}_READ"
        if any(event["name"] == bare_name for event in trace):
            fence_name = "SPANNER_ABSENT_TO_TERMINAL_FENCE_TRANSACTION" if case_id == "M04" else "ETCD_SAME_KEY_ABSENT_TO_TERMINAL_FENCE_CAS"
            confirm_name = "SPANNER_CONFIRMING_STRONG_READ" if case_id == "M04" else "ETCD_CONFIRMING_LINEARIZABLE_READ"
            conflict_name = "SPANNER_DELAYED_COMMIT_FENCE_CONFLICT" if case_id == "M04" else "ETCD_DELAYED_COMMIT_FENCE_CONFLICT"
            bare = _single_event(trace, bare_name)
            fence = _single_event(trace, fence_name)
            confirm = _single_event(trace, confirm_name)
            conflict = _single_event(trace, conflict_name)
            require(bare["sequence"] < fence["sequence"] < confirm["sequence"] < conflict["sequence"], "terminal fence event order drift")
            require({bare["details"]["operation_key"], fence["details"]["operation_key"], confirm["details"]["operation_key"], conflict["details"]["operation_key"]} == {expected_operation_key}, "terminal fence operation key drift")
            expected_read_consistency = "STRONG" if case_id == "M04" else "LINEARIZABLE"
            expected_fence_consistency = "SERIALIZABLE" if case_id == "M04" else "LINEARIZABLE_TOP_LEVEL_CAS"
            require(
                bare["details"]["consistency"] == expected_read_consistency
                and bare["details"]["revision"] == 0
                and fence["details"]["consistency"] == expected_fence_consistency
                and fence["details"]["revision"] == 1
                and confirm["details"]["consistency"] == expected_read_consistency
                and confirm["details"]["revision"] == 1
                and conflict["details"]["revision"] == 1,
                "terminal fence consistency/revision drift",
            )
            require(bare["details"]["result"] == "ABSENT" and bare["details"]["record_sha256"] == ZERO_SHA256 and bare["details"]["terminal"] is False, "bare absence treated as terminal")
            require(fence["details"]["compare_record_sha256"] == ZERO_SHA256 and fence["details"]["cas_result"] == "APPLIED", "terminal fence CAS drift")
            require(confirm["details"]["result"] == "TERMINAL_FENCE" and confirm["details"]["terminal"] is True, "terminal fence confirmation drift")
            expected_fence_record = _operation_state_record(
                schedule["simulation_run_id"],
                expected_exact_key_version,
                authority="FENCED_ABSENT",
                outbox="NONE",
                challenge_consumptions=0,
                logical_sink_reservations=0,
                terminal=True,
            )
            expected_fence_record["record_kind"] = "TERMINAL_FENCE"
            expected_fence_sha = sha256_value(expected_fence_record)
            expected_operation_sha = sha256_value(
                ExactKeyCASDouble.operation_record(
                    schedule["simulation_run_id"], expected_exact_key_version
                )
            )
            require(confirm["details"]["record_sha256"] == fence["details"]["committed_record_sha256"] == conflict["details"]["observed_record_sha256"] == expected_fence_sha, "terminal fence record hash drift")
            require(conflict["details"]["delayed_record_sha256"] == expected_operation_sha, "delayed operation record hash drift")
            require(
                conflict["details"]["compare_record_sha256"] == ZERO_SHA256
                and conflict["details"]["cas_result"] == "CONFLICT_NO_MUTATION",
                "delayed commit bypassed fence",
            )
            require(
                row["state"]["durable_operation_record_sha256"]
                == expected_fence_sha
                and row["state"]["durable_operation_revision"] == 1,
                "terminal fence durable state binding drift",
            )

    for lookup_name in ("SPANNER_EXACT_STRONG_LOOKUP", "ETCD_EXACT_LINEARIZABLE_LOOKUP"):
        for lookup in [event for event in trace if event["name"] == lookup_name]:
            expected_consistency = "STRONG" if lookup_name.startswith("SPANNER_") else "LINEARIZABLE"
            require(
                lookup["details"]["operation_key"] == expected_operation_key
                and lookup["details"]["record_sha256"]
                == sha256_value(
                    ExactKeyCASDouble.operation_record(
                        schedule["simulation_run_id"], expected_exact_key_version
                    )
                )
                and lookup["details"]["result"] == "EXACT_OPERATION_RECORD"
                and lookup["details"]["terminal"] is False,
                "exact operation lookup drift",
            )
            require(
                lookup["details"]["consistency"] == expected_consistency
                and lookup["details"]["revision"] == 1,
                "exact operation lookup consistency/revision drift",
            )
            require(
                row["state"]["durable_operation_record_sha256"]
                == lookup["details"]["record_sha256"]
                and row["state"]["durable_operation_revision"] == 1,
                "exact operation durable state binding drift",
            )

    if case_id == "S12":
        route = _single_event(trace, "OPENBAO_ROUTE_EXECUTION_EVIDENCE")["details"]
        seal = _single_event(trace, "OPENBAO_DIRECT_TARGET_SEAL_STATUS")["details"]
        require(seal["sealed"] is True and seal["service_wide_unavailable_inferred"] is False, "S12 seal inference drift")
        require(seal["target_node"] == route["target_node"] and seal["cluster_id"] == route["cluster_id"], "S12 target correlation drift")
        success = (row["simulated_classification"] or row["case_classification"]) == "CONFORMING_OBSERVED"
        if success:
            require(route["route_node"] != route["executing_node"] != route["target_node"], "S12 successor separation drift")
            require(route["executing_ha_role"] == "PERFORMANCE_STANDBY_ACTIVE", "S12 HA role drift")
            require(route["redirect_node"] == route["executing_node"] and route["forwarded_by_node"] == route["route_node"], "S12 redirect/forward drift")
            require(route["redirect_forward_audit_bound"] is True and route["audit_record_sha256"] and route["wire_attempt_sha256"], "S12 audit/wire binding missing")
            require(
                route["audit_record_sha256"]
                == _framed_hash(
                    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/s12-audit",
                    schedule["simulation_run_id"],
                    route["cluster_id"],
                    route["request_id"],
                    route["route_node"],
                    route["executing_node"],
                ),
                "S12 audit record hash drift",
            )
            require(
                route["wire_attempt_sha256"]
                == _framed_hash(
                    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/s12-wire-attempt",
                    schedule["simulation_run_id"],
                    route["cluster_id"],
                    route["request_id"],
                    route["executing_node"],
                ),
                "S12 wire attempt hash drift",
            )
            require(call_events and receipt_events, "S12 success lacks call/receipt")
            for event in (call_events[0], validation_events[0], receipt_events[0]):
                require(
                    event["details"]["execution_request_id"] == route["request_id"]
                    and event["details"]["executing_node"] == route["executing_node"]
                    and event["details"]["execution_cluster_id"] == route["cluster_id"]
                    and event["details"]["audit_record_sha256"] == route["audit_record_sha256"]
                    and event["details"]["wire_attempt_sha256"] == route["wire_attempt_sha256"],
                    "S12 call/receipt correlation drift",
                )
        else:
            require(route["executing_node"] is None and route["executing_ha_role"] is None, "S12 failure preclaims executor")
            require(route["redirect_node"] is None and route["forwarded_by_node"] is None, "S12 failure preclaims routing")
            require(route["audit_record_sha256"] is None and route["wire_attempt_sha256"] is None, "S12 failure preclaims audit/wire")
            require(not call_events and not receipt_events and row["state"]["emitted_outputs"] == 0, "S12 failure accepted work")
            unavailable = _single_event(
                trace,
                "OPENBAO_STANDBY_TAKEOVER_UNAVAILABLE_FAIL_CLOSED",
            )["details"]
            require(
                unavailable
                == {
                    "cluster_id": route["cluster_id"],
                    "request_id": route["request_id"],
                    "accepted_receipts": 0,
                    "emitted_outputs": 0,
                },
                "S12 fail-closed result drift",
            )


def _replay_expected_outcome(
    row: dict[str, Any],
    contract: dict[str, Any],
    configuration: dict[str, Any],
) -> tuple[CaseOutcome, SimulationState]:
    schedule = row["schedule"]
    _, case = _contract_index(contract)[
        (schedule["track_id"], schedule["case_id"])
    ]
    expected_variant = expected_injection_variant(
        case, schedule["repetition_index"]
    )
    state = SimulationState()
    state.event(
        "ASSIGNMENT_HASH_SEALED",
        assignment_sha256=schedule["assignment_sha256"],
        simulation_run_id=schedule["simulation_run_id"],
    )
    controller = OneShotFaultController(
        assignment_sha256=schedule["assignment_sha256"],
        case_id=schedule["case_id"],
        injection_cut=case["injection_cut"],
        injection_variant=expected_variant,
        trigger_limit=0 if case["injection_cut"] == "NONE" else 1,
    )
    controller.arm(state)
    controller.start_candidate(state)
    if schedule["track_id"] == MANAGED_TRACK:
        outcome = _managed_case(
            schedule["case_id"],
            schedule["repetition_index"],
            state,
            configuration,
            controller,
        )
    else:
        outcome = _self_hosted_case(
            schedule["case_id"],
            schedule["repetition_index"],
            state,
            configuration,
            controller,
        )
    if outcome.final_state is not None:
        state = outcome.final_state
    controller.finish(state)
    return outcome, state


def validate_run_row(
    row: Any,
    contract: dict[str, Any],
    configuration: dict[str, Any],
) -> None:
    exact_keys(row, RUN_ROW_FIELDS, "run row")
    require(row["schema"] == RUN_ROW_SCHEMA, "run row schema drift")
    require(row["harness_mode"] == HARNESS_MODE, "run row mode drift")
    require(row["contract_sha256"] == CONTRACT_SHA256, "run row contract drift")
    require(row["counts_toward_experiment"] is False, "synthetic row counts toward experiment")
    require(row["experimental_run_row"] is False, "synthetic row marked experimental")
    require(row["retained"] is True, "row was excluded")
    require(row["boundary"] == BOUNDARY, "run row boundary drift")
    schedule = row["schedule"]
    exact_keys(
        schedule,
        {
            "track_id", "case_id", "repetition_index", "block_position",
            "assignment_sha256", "configuration_sha256", "simulation_run_id",
            "namespace_id", "assignment_before_candidate_start",
            "injection_armed_before_candidate_start",
        },
        "run schedule",
    )
    require(schedule["track_id"] in {MANAGED_TRACK, SELF_HOSTED_TRACK}, "row track drift")
    require(type(schedule["repetition_index"]) is int and 1 <= schedule["repetition_index"] <= 30, "repetition drift")
    require(type(schedule["block_position"]) is int and schedule["block_position"] > 0, "block position drift")
    for field_name in ("assignment_sha256", "configuration_sha256", "simulation_run_id", "namespace_id"):
        value = schedule[field_name]
        require(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value), f"{field_name} drift")
    require(schedule["assignment_before_candidate_start"] is True, "late assignment")
    require(schedule["injection_armed_before_candidate_start"] is True, "late injection arm")
    require(
        schedule["configuration_sha256"] == sha256_value(configuration),
        "row configuration binding drift",
    )

    index = _contract_index(contract)
    require((schedule["track_id"], schedule["case_id"]) in index, "row case join failed")
    track, case = index[(schedule["track_id"], schedule["case_id"])]
    case_meta = row["case"]
    exact_keys(
        case_meta,
        {"family", "planned_evidence_locus", "actual_evidence_origin", "injection_cut", "injection_variant"},
        "row case metadata",
    )
    require(case_meta["family"] == case["family"], "case family drift")
    require(case_meta["planned_evidence_locus"] == case["evidence_locus"], "planned locus drift")
    require(case_meta["injection_cut"] == case["injection_cut"], "injection cut drift")
    expected_outcome, expected_replay_state = _replay_expected_outcome(
        row, contract, configuration
    )
    require(
        case_meta["injection_variant"] == expected_outcome.injection_variant,
        "injection variant drift",
    )

    non_evaluable = row["row_outcome"] in {
        "OFFLINE_INFRASTRUCTURE_FAILURE_RETAINED",
        "OFFLINE_BOUNDARY_BREACH_ABORT_RETAINED",
    }
    if case["evidence_locus"] == "CLIENT_CONFORMANCE_DOUBLE":
        require(row["row_kind"] == "CLIENT_CONFORMANCE_OBSERVATION", "client row kind drift")
        require(case_meta["actual_evidence_origin"] == "OFFLINE_CLIENT_CONFORMANCE_DOUBLE", "client origin drift")
        require(
            row["evidence_class"]
            == "OFFLINE_CLIENT_CONFORMANCE_OBSERVATION_NOT_PROVIDER_OR_LAB_EVIDENCE",
            "client evidence class drift",
        )
        if not non_evaluable:
            require(row["counts_toward_harness_conformance"] is True, "client observation excluded from harness conformance")
            require(row["case_classification"] in case["allowed_classifications"], "client classification drift")
            require(row["simulated_classification"] is None, "client observation duplicated as model class")
            require(row["classification_scope"] == "CLIENT_CONFORMANCE_DOUBLE_ONLY", "client classification scope drift")
            require(row["row_outcome"] == "OFFLINE_CLIENT_CONFORMANCE_COMPLETED", "client row outcome drift")
    else:
        require(row["row_kind"] == "MODEL_SCENARIO", "model row kind drift")
        require(case_meta["actual_evidence_origin"] == "OFFLINE_MODEL_SCENARIO", "model origin drift")
        require(row["evidence_class"] == "OFFLINE_MODEL_SCENARIO_ONLY_NOT_OBSERVATION", "model evidence class drift")
        if not non_evaluable:
            require(row["counts_toward_harness_conformance"] is False, "model row counted as client conformance")
            require(row["case_classification"] is None, "model scenario claims experimental classification")
            require(row["simulated_classification"] in case["allowed_classifications"], "model oracle classification drift")
            require(row["classification_scope"] == "MODEL_SCENARIO_ONLY", "model classification scope drift")
            require(row["row_outcome"] == "OFFLINE_MODEL_SCENARIO_COMPLETED", "model row outcome drift")
    if non_evaluable:
        require(row["case_classification"] is None, "non-evaluable row has case classification")
        require(row["simulated_classification"] is None, "non-evaluable row has simulated classification")
        require(row["classification_scope"] == "NOT_EVALUABLE_RETAINED", "non-evaluable scope drift")
        require(row["counts_toward_harness_conformance"] is False, "non-evaluable row counted")
        require(row["oracle_classification_allowed"] is False, "non-evaluable row marked allowed")
    else:
        require(row["oracle_classification_allowed"] is True, "oracle classification not accepted")
    require(row["explicit_invariant_ids"] == case["invariant_ids"], "explicit invariant refs drift")
    expected_branch = (
        ["S10", "S11", "S12"]
        if schedule["case_id"] == "S12"
        and (row["simulated_classification"] or row["case_classification"])
        == "CONFORMING_OBSERVED"
        else []
    )
    require(row["branch_invariant_ids"] == expected_branch, "branch invariant refs drift")
    effective = row["effective_invariant_ids"]
    require(type(effective) is list and effective == sorted(set(effective)), "effective invariants not unique sorted")
    expected_effective = sorted(
        set(GLOBAL_INVARIANT_IDS) | set(case["invariant_ids"]) | set(expected_branch)
    )
    require(effective == expected_effective, "effective invariant closure drift")
    catalog_ids = {
        invariant["invariant_id"] for invariant in contract["global_invariants"]
    }
    for catalog_track in contract["tracks"]:
        catalog_ids.update(
            invariant["invariant_id"] for invariant in catalog_track["invariants"]
        )
    require(set(effective) <= catalog_ids, "effective invariant id does not resolve")

    trace = row["event_trace"]
    require(type(trace) is list, "event trace must be a list")
    require([event["sequence"] for event in trace] == list(range(1, len(trace) + 1)), "event sequence drift")
    state = row["state"]
    exact_keys(state, STATE_FIELDS, "run state")
    require(
        trace == expected_replay_state.events,
        "row event trace differs from deterministic candidate replay",
    )
    require(
        state == expected_replay_state.snapshot(),
        "row state differs from deterministic candidate replay",
    )
    expected_core = _expected_core_state(
        schedule["case_id"], schedule["repetition_index"]
    )
    require(
        all(state[field_name] == expected for field_name, expected in expected_core.items()),
        "run core authority/outbox state drift",
    )
    _validate_event_trace(row)
    evidence = row["evidence"]
    require(type(evidence) is dict, "row evidence must be an object")
    exact_keys(evidence, EVIDENCE_FIELDS, "row evidence")
    require(evidence["provider_evidence_sha256"] is None, "simulator trace masquerades as provider evidence")
    require(evidence["simulator_trace_sha256"] == sha256_value(trace), "simulator trace hash drift")
    require(evidence["pre_state_sha256"] == sha256_value(SimulationState().snapshot()), "pre-state hash drift")
    require(evidence["post_state_sha256"] == sha256_value(state), "post-state hash drift")
    require(evidence["real_provider_calls"] == 0, "real provider call claimed")
    require(evidence["emitted_outputs"] == 0, "output emitted")
    require(evidence["message_sha256"] == MESSAGE_SHA256 and evidence["message_bytes"] == 137, "message KAT drift")
    expected_evidence = {
        "request_sha256": expected_outcome.request_sha256,
        "response_sha256": expected_outcome.response_sha256,
        "requested_key_version": expected_outcome.requested_key_version,
        "validated_key_version": expected_outcome.validated_key_version,
        "requested_isolation": expected_outcome.requested_isolation,
        "effective_isolation": expected_outcome.effective_isolation,
        "test_signature_sha256": TEST_SIGNATURE_SHA256,
        "message_sha256": MESSAGE_SHA256,
        "message_bytes": len(MESSAGE),
        "public_key_sha256": expected_outcome.evidence_public_key_sha256,
        "semantic_tokens": expected_outcome.semantic_tokens,
    }
    require(
        all(
            evidence[field_name] == expected
            for field_name, expected in expected_evidence.items()
        ),
        "row exact evidence expectation drift",
    )
    semantic_tokens = evidence["semantic_tokens"]
    require(
        type(semantic_tokens) is list
        and len(semantic_tokens) == len(set(semantic_tokens))
        and all(type(token) is str and token for token in semantic_tokens),
        "semantic token shape drift",
    )
    forbidden_semantic_tokens = {
        "PROVIDER_PROCESSING_OBSERVED",
        "PROVIDER_EVIDENCE_PRESENT",
        "PRODUCTION_READY",
        "OUTPUT_PERMIT_GRANTED",
        "EXACTLY_ONCE_PROVEN",
        "REAL_PROVIDER_CALL",
    } | set(case["forbidden_claims"])
    require(
        not (set(semantic_tokens) & forbidden_semantic_tokens),
        "forbidden semantic claim token",
    )
    require(evidence["simulated_application_calls"] == state["simulated_application_calls"], "evidence/state call counter drift")
    require(evidence["simulated_processing_events"] == state["simulated_processing_events"], "evidence/state processing counter drift")
    require(evidence["restarts"] == state["restarts"], "evidence/state restart counter drift")
    require(evidence["emitted_outputs"] == state["emitted_outputs"] == 0, "evidence/state output counter drift")
    require(
        (state["receipt"] == "SIGNATURE_RECEIPT_COMMITTED")
        == (state["receipt_binding_sha256"] != ZERO_SHA256),
        "receipt state/binding drift",
    )
    assertions = row["assertions"]
    require(type(assertions) is dict and assertions and all(value is True for value in assertions.values()), "run assertion failed")
    require(row["claim_ceiling"] == track["claim_ceiling"], "claim ceiling drift")
    require(row["forbidden_claims"] == case["forbidden_claims"], "forbidden claims drift")


def build_suite_receipt(
    contract: dict[str, Any], configuration: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    schedule = build_schedule(contract, configuration)
    rows = [execute_schedule_entry(contract, configuration, entry) for entry in schedule]
    client_rows = [row for row in rows if row["row_kind"] == "CLIENT_CONFORMANCE_OBSERVATION"]
    model_rows = [row for row in rows if row["row_kind"] == "MODEL_SCENARIO"]
    require(len(client_rows) == 420, "client-conformance row cardinality drift")
    require(len(model_rows) == 600, "model-scenario row cardinality drift")
    variant_counts: dict[str, int] = {}
    classification_counts: dict[str, int] = {}
    for row in rows:
        variant_key = f"{row['schedule']['case_id']}:{row['case']['injection_variant']}"
        variant_counts[variant_key] = variant_counts.get(variant_key, 0) + 1
        classification = row["case_classification"] or row["simulated_classification"]
        classification_counts[classification] = classification_counts.get(classification, 0) + 1
    receipt = {
        "schema": SUITE_RECEIPT_SCHEMA,
        "harness_mode": HARNESS_MODE,
        "status": STATUS,
        "decision": DECISION,
        "contract_sha256": CONTRACT_SHA256,
        "configuration_sha256": sha256_value(configuration),
        "schedule_sha256": sha256_value([entry.as_dict() for entry in schedule]),
        "offline_rows_sha256": sha256_value(rows),
        "counts": {
            "tracks": 2,
            "cases": 34,
            "repetitions_per_case": 30,
            "offline_synthetic_rows": 1020,
            "client_conformance_observation_rows": len(client_rows),
            "model_scenario_rows": len(model_rows),
            "managed_service_observation_rows": 0,
            "owned_lab_observation_rows": 0,
            "provider_evidence_rows": 0,
            "experimental_run_rows": 0,
            "planned_experiment_rows_satisfied": 0,
        },
        "track_results": {
            MANAGED_TRACK: "NOT_EVALUATED_INCOMPLETE_MANAGED_SERVICE_EVIDENCE_LOCUS",
            SELF_HOSTED_TRACK: "NOT_EVALUATED_INCOMPLETE_OWNED_LAB_EVIDENCE_LOCUS",
        },
        "classification_counts": dict(sorted(classification_counts.items())),
        "variant_counts": dict(sorted(variant_counts.items())),
        "data_quality": {
            "schedule_completeness": "PASS_1020_OFFLINE_ROWS_ONLY",
            "run_key_uniqueness": "PASS_OFFLINE_NAMESPACE_ONLY",
            "assignment_balance": "PASS_30_OFFLINE_BLOCKS_PER_TRACK",
            "variant_balance": "PASS_FROZEN_MODULO_RULES",
            "provenance": "PASS_PLANNED_LOCUS_SEPARATE_FROM_ACTUAL_OFFLINE_ORIGIN",
            "provider_experiment_completeness": "NOT_EVALUATED_ZERO_EXPERIMENT_ROWS",
            "post_outcome_exclusions": 0,
        },
        "contract_interpretations": [
            "ALL_GLOBAL_X01_TO_X08_INVARIANTS_ARE_UNIONED_INTO_EVERY_CASE",
            "S12_SUCCESS_ADDS_S10_S11_S12_FULL_SIGNING_VALIDATION_WHILE_FAIL_BRANCH_REQUIRES_ZERO_ACCEPTED_RECEIPT",
            "PROVIDER_EVIDENCE_HASH_IS_NULL_FOR_ALL_OFFLINE_ROWS_AND_SIMULATOR_TRACE_HAS_A_SEPARATE_HASH",
            "ROW_OUTCOME_IS_SEPARATE_FROM_CASE_OR_SIMULATED_CLASSIFICATION",
            "CLIENT_DOUBLE_ROWS_AND_MODEL_SCENARIOS_NEVER_SATISFY_THE_PROVIDER_EXPERIMENT_DENOMINATOR",
        ],
        "boundary": BOUNDARY,
        "known_limitations": [
            "PURE_IN_PROCESS_DOUBLES_DO_NOT_MODEL_PROVIDER_NETWORK_SCHEDULER_STORAGE_OR_HA_IMPLEMENTATIONS",
            "MODEL_SCENARIOS_ARE_NOT_MANAGED_SERVICE_OR_OWNED_LAB_OBSERVATIONS",
            "CLIENT_CONFORMANCE_OBSERVATIONS_DO_NOT_PROVE_PROVIDER_PROCESSING",
            "FIXED_TEST_ED25519_SEED_AND_REFERENCE_ARITHMETIC_ARE_NOT_PRODUCTION_KEY_HANDLING",
            "ONE_SIMULATED_CALL_OR_RECEIPT_DOES_NOT_PROVE_ONE_PROVIDER_RPC_OR_SIGNATURE_CREATION",
            "NO_TRACK_RESULT_PRODUCTION_READINESS_OR_OUTPUT_PERMIT_IS_AVAILABLE",
        ],
        "next_unit": NEXT_UNIT,
    }
    return receipt, rows
