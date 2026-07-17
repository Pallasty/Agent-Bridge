#!/usr/bin/env python3
"""Pure offline authority verifier and adapter/control doubles for runner v1.

The module performs no filesystem, environment, clock, process, credential, or
network I/O.  Every key and capability used here is deterministic test data.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Iterable

import biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1 as frozen_contract


STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_OFFLINE_AUTHORITY_VERIFIER_"
    "AND_ADAPTER_DOUBLES_IMPLEMENTED_NO_PROVIDER_NO_CREDENTIAL_NO_PERMIT"
)
DECISION = (
    "OFFLINE_AUTHORITY_VERIFIER_AND_ADAPTER_DOUBLES_PASS_"
    "RUNTIME_EXECUTION_REMAINS_BLOCKED"
)
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "OFFLINE_INTEGRATION_AND_RUNTIME_ADMISSION_BOUNDARY_REVIEW"
)
CONFORMANCE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "offline_authority_and_adapter_doubles_v1.conformance_receipt.v0"
)
ADAPTER_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "offline_adapter_double_receipt.v0"
)
STOP_DOUBLE_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "offline_stop_double_receipt.v0"
)
CONTROL_EVIDENCE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "offline_control_evidence.v0"
)
TRUST_POLICY_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "offline_trust_policy.v0"
)
SIGNATURE_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "offline_signature_verification_receipt.v0"
)


class OfflineDoubleError(ValueError):
    """Fail-closed rejection from the pure offline implementation."""


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise OfflineDoubleError(f"{code}: {message}")


def exact_keys(value: Any, expected: Iterable[str], code: str, label: str) -> None:
    require(type(value) is dict, code, f"{label} must be an object")
    require(set(value) == set(expected), code, f"{label} key closure drift")


def canonical_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
                separators=(",", ": "),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise OfflineDoubleError(f"E_CANONICAL: value is not canonical JSON: {exc}") from exc


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def tag_hash(tag: str) -> str:
    return sha256_bytes(tag.encode("utf-8"))


def framed_bytes(*parts: bytes) -> bytes:
    encoded = bytearray()
    for part in parts:
        encoded.extend(len(part).to_bytes(4, "big"))
        encoded.extend(part)
    return bytes(encoded)


def framed_hash(domain: str, *parts: bytes) -> str:
    return sha256_bytes(framed_bytes(domain.encode("utf-8"), *parts))


def parse_utc(value: Any, code: str, label: str) -> datetime:
    require(type(value) is str, code, f"{label} is not text")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise OfflineDoubleError(f"{code}: {label} is not strict calendar UTC") from exc
    require(parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value, code, f"{label} drift")
    return parsed


# Deterministic Ed25519 reference arithmetic. It is test-only and has no key
# loading surface, provider compatibility claim, or production use.
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
    return (
        (x1 * y2 + x2 * y1) * _inv(1 + product) % _Q,
        (y1 * y2 + x1 * x2) * _inv(1 - product) % _Q,
    )


def _scalarmult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = (0, 1)
    addend = point
    remaining = scalar
    while remaining:
        if remaining & 1:
            result = _edwards(result, addend)
        addend = _edwards(addend, addend)
        remaining >>= 1
    return result


def _encodepoint(point: tuple[int, int]) -> bytes:
    x, y = point
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _decodepoint(raw: bytes) -> tuple[int, int]:
    require(len(raw) == 32, "E_SIGNATURE_KEY", "Ed25519 public key length drift")
    encoded = int.from_bytes(raw, "little")
    y = encoded & ((1 << 255) - 1)
    sign = encoded >> 255
    require(y < _Q, "E_SIGNATURE_KEY", "Ed25519 public key y is noncanonical")
    x = _xrecover(y)
    require(not (x == 0 and sign == 1), "E_SIGNATURE_KEY", "Ed25519 sign drift")
    if (x & 1) != sign:
        x = _Q - x
    point = (x, y)
    require(
        (-x * x + y * y - 1 - _D * x * x * y * y) % _Q == 0,
        "E_SIGNATURE_KEY",
        "Ed25519 key is not on curve",
    )
    return point


def _hint(raw: bytes) -> int:
    return int.from_bytes(hashlib.sha512(raw).digest(), "little")


@lru_cache(maxsize=32)
def ed25519_public_key(seed: bytes) -> bytes:
    require(len(seed) == 32, "E_TEST_SEED", "test seed length drift")
    digest = hashlib.sha512(seed).digest()
    scalar = 2**254 + sum(
        2**index * ((digest[index // 8] >> (index & 7)) & 1)
        for index in range(3, 254)
    )
    return _encodepoint(_scalarmult(_B, scalar))


def ed25519_sign(message: bytes, seed: bytes) -> bytes:
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


@lru_cache(maxsize=256)
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
    except OfflineDoubleError:
        return False


@dataclass(frozen=True)
class AdapterSpec:
    adapter_id: str
    track_id: str
    credential_class: str
    allowed_operations: tuple[str, ...]
    forbidden_operations: tuple[str, ...]
    evidence_returns: tuple[str, ...]


@dataclass(frozen=True)
class StopControlSpec:
    interface_id: str
    credential_class: str
    allowed_operations: tuple[str, ...]
    forbidden_operations: tuple[str, ...]
    receipt_fields: tuple[str, ...]


MANAGED_TRACK = "MANAGED_SPANNER_CLOUD_KMS"
SELF_HOSTED_TRACK = "SELF_HOSTED_ETCD_OPENBAO"


def _adapter(
    adapter_id: str,
    track_id: str,
    credential_class: str,
    allowed: tuple[str, ...],
    forbidden: tuple[str, ...],
    evidence: tuple[str, ...],
) -> AdapterSpec:
    return AdapterSpec(adapter_id, track_id, credential_class, allowed, forbidden, evidence)


ADAPTER_CATALOG = {
    spec.adapter_id: spec
    for spec in (
        _adapter(
            "SPANNER_AUTHORITY_ADAPTER",
            MANAGED_TRACK,
            "MANAGED_SPANNER_DATA_PLANE",
            (
                "RUN_EXPLICIT_SERIALIZABLE_AUTHORITY_TRANSACTION",
                "STRONG_READ_EXACT_OPERATION_KEY",
                "CAS_ABSENT_TO_TERMINAL_FENCE",
                "PERSIST_PREPARED_ATTEMPT",
                "PERSIST_VALIDATED_RECEIPT",
                "QUARANTINE_ATTEMPT",
            ),
            (
                "EXTERNAL_SIDE_EFFECT_INSIDE_RETRYABLE_CLOSURE",
                "NON_SERIALIZABLE_AUTHORITY_TRANSACTION",
            ),
            (
                "REQUESTED_AND_EFFECTIVE_ISOLATION",
                "CLOSURE_ATTEMPT_RECEIPTS",
                "EXACT_RECORD_AND_REVISION",
                "TOP_LEVEL_COMMIT_OR_UNKNOWN_RECEIPT",
            ),
        ),
        _adapter(
            "CLOUD_KMS_SIGNER_ADAPTER",
            MANAGED_TRACK,
            "MANAGED_KMS_SIGN",
            (
                "SIGN_EXACT_137_RAW_BYTES_WITH_EXACT_VERSION",
                "RETURN_OPERATION_SPECIFIC_RESPONSE_EVIDENCE",
            ),
            (
                "DIGEST_ARM_SIGNING",
                "IMPLICIT_OR_PARENT_KEY_VERSION",
                "HIDDEN_TRANSPORT_RETRY",
            ),
            (
                "APPLICATION_CALL_RECEIPT",
                "REQUEST_AND_RESPONSE_SHA256",
                "VERSION_PROTECTION_CRC_AND_VERIFICATION_FIELDS",
            ),
        ),
        _adapter(
            "MANAGED_FAULT_PROXY_ADAPTER",
            MANAGED_TRACK,
            "MANAGED_FAULT_PROXY_CONTROL",
            (
                "ARM_EXACT_ASSIGNED_CUT",
                "TRIGGER_ONCE_FOR_EXACT_RUN_TRAFFIC",
                "RECORD_WIRE_ATTEMPTS_WITHOUT_PROCESSING_CLAIM",
            ),
            (
                "CROSS_NAMESPACE_FAULT",
                "MULTIPLE_TRIGGER",
                "PROVIDER_PROCESSING_INFERENCE",
            ),
            (
                "ARM_RECEIPT",
                "TRIGGER_RECEIPT",
                "CAUSAL_BINDING_SHA256",
                "WIRE_ATTEMPT_INDEX",
            ),
        ),
        _adapter(
            "MANAGED_EVIDENCE_COLLECTOR_ADAPTER",
            MANAGED_TRACK,
            "MANAGED_EVIDENCE_READ_ONLY",
            (
                "COLLECT_ALLOWLISTED_NON_SECRET_FIELDS",
                "HASH_IMMUTABLE_RAW_EVIDENCE_INDEX",
                "RETURN_OBSERVATIONS_ONLY",
            ),
            (
                "CASE_CLASSIFICATION",
                "CREDENTIAL_MATERIAL_CAPTURE",
                "OUTPUT_AUTHORIZATION",
            ),
            (
                "PROVIDER_PROFILE_SHA256",
                "RAW_EVIDENCE_INDEX_SHA256",
                "SAFE_EVENT_TRACE_SHA256",
            ),
        ),
        _adapter(
            "ETCD_AUTHORITY_ADAPTER",
            SELF_HOSTED_TRACK,
            "SELF_HOSTED_ETCD_DATA_PLANE",
            (
                "LINEARIZABLE_EXACT_READ",
                "NON_NESTED_NONLEASED_EXACT_KEY_CAS",
                "CAS_ABSENT_TO_TERMINAL_FENCE",
                "PERSIST_PREPARED_ATTEMPT",
                "PERSIST_VALIDATED_RECEIPT",
                "QUARANTINE_ATTEMPT",
            ),
            (
                "SERIALIZABLE_STALE_AUTHORITY_READ",
                "NESTED_TRANSACTION",
                "LEASED_AUTHORITY_KEY",
            ),
            (
                "SERIALIZABLE_FALSE_REQUEST_FIELD",
                "TOP_LEVEL_TRANSACTION_REVISION",
                "EXACT_RECORD_MOD_REVISION_AND_CAS_RECEIPT",
            ),
        ),
        _adapter(
            "OPENBAO_TRANSIT_ADAPTER",
            SELF_HOSTED_TRACK,
            "SELF_HOSTED_TRANSIT_SIGN",
            (
                "SIGN_SINGLE_NONBATCH_CONTEXT_FREE_EXACT_137_BYTE_INPUT",
                "RETURN_VERSIONED_SIGNATURE_OBSERVATION",
            ),
            (
                "IMPLICIT_LATEST_VERSION",
                "DERIVED_BATCH_CONTEXT_OR_PREHASH_MODE",
                "HIDDEN_TRANSPORT_RETRY",
            ),
            (
                "APPLICATION_CALL_RECEIPT",
                "REQUEST_RESPONSE_AND_VERSION_BINDINGS",
                "ROUTE_AND_REQUEST_IDENTITIES",
            ),
        ),
        _adapter(
            "EXTERNAL_RESTORE_WITNESS_ADAPTER",
            SELF_HOSTED_TRACK,
            "SELF_HOSTED_EXTERNAL_WITNESS",
            (
                "CURRENT_LINEARIZABLE_READ",
                "COMPARE_EXACT_PREVIOUS_HASH_AND_GENERATION_THEN_PUT",
            ),
            (
                "SHARED_RESTORE_ACTOR_CREDENTIAL",
                "WITNESS_INSIDE_ETCD_SNAPSHOT_OR_RESTORE_DOMAIN",
            ),
            (
                "FIFTEEN_FIELD_WITNESS_RECORD",
                "WITNESS_KEY_HASH_GENERATION_AND_CAS_RECEIPT",
            ),
        ),
        _adapter(
            "LAB_FAULT_CONTROLLER_ADAPTER",
            SELF_HOSTED_TRACK,
            "SELF_HOSTED_LAB_FAULT_CONTROL",
            (
                "ARM_EXACT_ASSIGNED_LAB_CUT",
                "TRIGGER_ONCE_INSIDE_EXACT_RUN_NAMESPACE",
                "RECORD_TOPOLOGY_AND_CAUSAL_BINDING",
            ),
            (
                "CROSS_RUN_OR_CROSS_TRACK_FAULT",
                "MULTIPLE_TRIGGER",
                "UNSCOPED_RESTORE_OR_SEAL_ACTION",
            ),
            (
                "ARM_RECEIPT",
                "TRIGGER_RECEIPT",
                "TOPOLOGY_SHA256",
                "CAUSAL_BINDING_SHA256",
            ),
        ),
        _adapter(
            "SELF_HOSTED_EVIDENCE_COLLECTOR_ADAPTER",
            SELF_HOSTED_TRACK,
            "SELF_HOSTED_EVIDENCE_READ_ONLY",
            (
                "COLLECT_ALLOWLISTED_NON_SECRET_FIELDS",
                "HASH_IMMUTABLE_LAB_EVIDENCE_INDEX",
                "CORRELATE_ROUTE_EXECUTOR_AUDIT_AND_WIRE_IDENTITIES",
                "RETURN_OBSERVATIONS_ONLY",
            ),
            (
                "CASE_CLASSIFICATION",
                "CREDENTIAL_MATERIAL_CAPTURE",
                "OUTPUT_AUTHORIZATION",
            ),
            (
                "PROVIDER_PROFILE_SHA256",
                "RAW_EVIDENCE_INDEX_SHA256",
                "SAFE_EVENT_TRACE_SHA256",
            ),
        ),
    )
}


def _control(
    interface_id: str,
    credential_class: str,
    allowed: tuple[str, ...],
    forbidden: tuple[str, ...],
    receipt_fields: tuple[str, ...],
) -> StopControlSpec:
    return StopControlSpec(interface_id, credential_class, allowed, forbidden, receipt_fields)


STOP_CONTROL_CATALOG = {
    spec.interface_id: spec
    for spec in (
        _control(
            "CAPABILITY_FENCE_CONTROL",
            "STOP_CAPABILITY_FENCE_CONTROL",
            ("CAS_EXACT_RUN_CAPABILITY_TO_STOP_FENCED", "BLOCK_NEW_CALLS_FOR_EXACT_RUN"),
            ("UNFENCE_OR_REAUTHORIZE_EXECUTION", "CROSS_RUN_FENCE"),
            (
                "CONTROL_LEDGER_REVISION",
                "CAPABILITY_COMMITMENT_SHA256",
                "FENCE_RECEIPT_SHA256",
            ),
        ),
        _control(
            "FAULT_DISARM_AND_EGRESS_ISOLATION_CONTROL",
            "STOP_FAULT_DISARM_EGRESS_CONTROL",
            ("DISARM_EXACT_ASSIGNED_CUT", "ISOLATE_EXACT_ASSIGNED_RUN_EGRESS"),
            ("ARM_OR_TRIGGER_FAULT", "CROSS_NAMESPACE_CONTROL"),
            ("DISARM_RECEIPT_SHA256", "EGRESS_ISOLATION_RECEIPT_SHA256"),
        ),
        _control(
            "CREDENTIAL_BROKER_REVOCATION_CONTROL",
            "STOP_CREDENTIAL_REVOCATION_CONTROL",
            (
                "REVOKE_EXACT_RUN_CREDENTIAL_LEASES",
                "CONFIRM_ZERO_ACTIVE_LEASE_COMMITMENTS",
            ),
            ("ISSUE_OR_RENEW_CREDENTIAL", "REVOKE_OUTSIDE_EXACT_RUN_SCOPE"),
            ("REVOCATION_RECEIPT_SHA256", "ACTIVE_LEASE_COMMITMENTS_AFTER_STOP"),
        ),
        _control(
            "DURABLE_EVIDENCE_RETENTION_CONTROL",
            "STOP_DURABLE_EVIDENCE_RETENTION_CONTROL",
            (
                "PERSIST_CURRENT_ROW_DURABLE_STATE_AND_SAFE_EVIDENCE",
                "CONFIRM_RETENTION_BINDINGS",
            ),
            ("DELETE_OR_RECLASSIFY_RETAINED_ROW", "PERSIST_SECRET_MATERIAL"),
            (
                "CURRENT_RETAINED_ROW_SHA256",
                "EVIDENCE_BUNDLE_SHA256",
                "RETENTION_RECEIPT_SHA256",
            ),
        ),
        _control(
            "SCOPED_RESOURCE_CLEANUP_CONTROL",
            "STOP_SCOPED_RESOURCE_CLEANUP_CONTROL",
            ("FREEZE_EXACT_ASSIGNED_RESOURCES", "REDUCTIVE_TEARDOWN_WITHIN_EXACT_CLEANUP_SCOPE"),
            ("CREATE_OR_EXPAND_RESOURCE_SCOPE", "DELETE_EVIDENCE_AUTHORITY_OR_RETAINED_ROW"),
            (
                "CLEANUP_CAPABILITY_COMMITMENT_SHA256",
                "CLEANUP_STATUS",
                "CLEANUP_COMPLETION_RECEIPT_SHA256",
            ),
        ),
    )
}


class OfflineEvidenceStore:
    """Duplicate-free in-memory allowlist for canonical evidence and signatures."""

    def __init__(self) -> None:
        self._documents: dict[str, dict[str, Any]] = {}
        self._signatures: dict[str, bytes] = {}

    def add_document(self, document: dict[str, Any]) -> str:
        document_copy = copy.deepcopy(document)
        digest = sha256_value(document_copy)
        previous = self._documents.get(digest)
        require(
            previous is None or previous == document_copy,
            "E_EVIDENCE_DUPLICATE",
            "conflicting document under one digest",
        )
        self._documents[digest] = document_copy
        return digest

    def add_signature(self, signature: bytes) -> str:
        require(type(signature) is bytes, "E_SIGNATURE_TYPE", "signature must be bytes")
        digest = sha256_bytes(signature)
        previous = self._signatures.get(digest)
        require(
            previous is None or previous == signature,
            "E_EVIDENCE_DUPLICATE",
            "conflicting signature under one digest",
        )
        self._signatures[digest] = signature
        return digest

    def resolve_document(self, digest: str, code: str, label: str) -> dict[str, Any]:
        require(digest in self._documents, code, f"{label} is missing")
        document = copy.deepcopy(self._documents[digest])
        require(sha256_value(document) == digest, code, f"{label} digest mismatch")
        return document

    def resolve_signature(self, digest: str, code: str, label: str) -> bytes:
        require(digest in self._signatures, code, f"{label} is missing")
        signature = self._signatures[digest]
        require(sha256_bytes(signature) == digest, code, f"{label} digest mismatch")
        return signature

    def clone(self) -> "OfflineEvidenceStore":
        result = OfflineEvidenceStore()
        result._documents = copy.deepcopy(self._documents)
        result._signatures = dict(self._signatures)
        return result


_LEDGER_BINDING_FIELDS = (
    "adapter_id",
    "assignment_sha256",
    "case_id",
    "effective_allowed_operations",
    "field_level_intersection_sha256",
    "namespace_id",
    "phase",
    "repetition_index",
    "simulation_run_id",
    "suite_id",
    "track_id",
)


class PrivateCapabilityControlLedgerDouble:
    """Single-use in-memory CAS ledger bound to one private test capability."""

    def __init__(
        self,
        bindings: dict[str, Any],
        private_capability: bytes,
    ) -> None:
        exact_keys(bindings, _LEDGER_BINDING_FIELDS, "E_LEDGER_BINDINGS", "ledger bindings")
        require(
            type(private_capability) is bytes and len(private_capability) == 32,
            "E_CAPABILITY_BYTES",
            "private capability must be exactly 32 bytes",
        )
        self._bindings = copy.deepcopy(bindings)
        self._secret_sha256 = sha256_bytes(private_capability)
        self._capability_commitment_sha256: str | None = None
        self._state = "UNUSED"
        self._revision = 0
        self._stop_fenced = False
        self._anchor_record = {
            "adapter_id": bindings["adapter_id"],
            "assignment_sha256": bindings["assignment_sha256"],
            "binding_sha256": sha256_value(bindings),
            "case_id": bindings["case_id"],
            "namespace_id": bindings["namespace_id"],
            "phase": bindings["phase"],
            "private_capability_secret_sha256": self._secret_sha256,
            "repetition_index": bindings["repetition_index"],
            "revision": 0,
            "schema": (
                "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
                "runner_v1.offline_control_ledger_anchor.v0"
            ),
            "simulation_run_id": bindings["simulation_run_id"],
            "state": "UNUSED",
            "stop_fenced": False,
            "suite_id": bindings["suite_id"],
            "track_id": bindings["track_id"],
        }
        self._anchor_sha256 = framed_hash(
            frozen_contract.CONTROL_LEDGER_DOMAIN,
            canonical_bytes(self._anchor_record),
        )

    @property
    def anchor_sha256(self) -> str:
        return self._anchor_sha256

    @property
    def state(self) -> str:
        return self._state

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def stop_fenced(self) -> bool:
        return self._stop_fenced

    @property
    def adapter_id(self) -> str:
        return self._bindings["adapter_id"]

    def verify_secret(self, private_capability: bytes) -> None:
        require(
            type(private_capability) is bytes
            and len(private_capability) == 32
            and sha256_bytes(private_capability) == self._secret_sha256,
            "E_LEDGER_SECRET",
            "private capability does not match ledger anchor",
        )

    def bind_capability_commitment(self, commitment_sha256: str) -> None:
        require(
            self._capability_commitment_sha256 in (None, commitment_sha256),
            "E_LEDGER_COMMITMENT",
            "ledger capability commitment rebinding",
        )
        self._capability_commitment_sha256 = commitment_sha256

    def start(self, capability: "VerifiedCapability") -> None:
        self._require_capability(capability)
        require(not self._stop_fenced, "E_LEDGER_STOP_FENCED", "capability is stop fenced")
        require(self._state == "UNUSED", "E_LEDGER_START_CAS", "start CAS is not UNUSED")
        self._state = "START_COMMITTED"
        self._revision += 1

    def consume(self, capability: "VerifiedCapability", adapter_id: str, operation: str) -> None:
        self._require_capability(capability)
        require(not self._stop_fenced, "E_LEDGER_STOP_FENCED", "capability is stop fenced")
        require(self._state == "START_COMMITTED", "E_LEDGER_CONSUME_CAS", "call CAS is not start committed")
        require(adapter_id == self.adapter_id, "E_ADAPTER_SCOPE", "adapter identity mismatch")
        require(
            operation in self._bindings["effective_allowed_operations"],
            "E_OPERATION_SCOPE",
            "operation is outside exact capability scope",
        )
        self._state = "CALL_CONSUMED"
        self._revision += 1

    def fence_for_stop(self) -> None:
        require(
            self._state not in ("STOP_ABSORBING_COMPLETE", "STOP_FAILED_QUARANTINED"),
            "E_STOP_TERMINAL",
            "terminal stop state cannot transition",
        )
        self._stop_fenced = True
        self._state = "STOP_FENCING"
        self._revision += 1

    def finish_stop(self, success: bool) -> None:
        require(self._stop_fenced, "E_STOP_FENCE", "stop completion without fence")
        require(self._state == "STOP_FENCING", "E_STOP_STATE", "stop completion state drift")
        self._state = "STOP_ABSORBING_COMPLETE" if success else "STOP_FAILED_QUARANTINED"
        self._revision += 1

    def clone_started_for_stop_test(self) -> "PrivateCapabilityControlLedgerDouble":
        result = object.__new__(PrivateCapabilityControlLedgerDouble)
        result._bindings = copy.deepcopy(self._bindings)
        result._secret_sha256 = self._secret_sha256
        result._capability_commitment_sha256 = self._capability_commitment_sha256
        result._state = "START_COMMITTED"
        result._revision = 1
        result._stop_fenced = False
        result._anchor_record = copy.deepcopy(self._anchor_record)
        result._anchor_sha256 = self._anchor_sha256
        return result

    def _require_capability(self, capability: "VerifiedCapability") -> None:
        require(type(capability) is VerifiedCapability, "E_CAPABILITY_TYPE", "unverified capability")
        require(capability._ledger is self, "E_CAPABILITY_LEDGER", "capability/ledger mismatch")
        require(
            self._capability_commitment_sha256 == capability.commitment_sha256,
            "E_CAPABILITY_COMMITMENT",
            "capability commitment mismatch",
        )


class VerifiedCapability:
    """Process-local bearer of test-only private bytes; deliberately nonserializable."""

    __slots__ = ("_bundle", "_ledger", "_private_capability")

    def __init__(
        self,
        bundle: dict[str, Any],
        ledger: PrivateCapabilityControlLedgerDouble,
        private_capability: bytes,
    ) -> None:
        self._bundle = copy.deepcopy(bundle)
        self._ledger = ledger
        self._private_capability = bytes(private_capability)

    @property
    def commitment_sha256(self) -> str:
        return self._bundle["execution_capability_commitment"][
            "capability_commitment_sha256"
        ]

    @property
    def adapter_id(self) -> str:
        return self._ledger.adapter_id

    @property
    def track_id(self) -> str:
        return self._bundle["track_id"]

    @property
    def case_id(self) -> str:
        return self._bundle["case_id"]

    @property
    def repetition_index(self) -> int:
        return self._bundle["repetition_index"]

    @property
    def simulation_run_id(self) -> str:
        return self._bundle["simulation_run_id"]

    @property
    def namespace_id(self) -> str:
        return self._bundle["namespace_id"]

    def __getstate__(self) -> None:
        raise TypeError("private capability is nonserializable")

    def __reduce__(self) -> None:
        raise TypeError("private capability is nonserializable")


_SIGNATURE_RECEIPT_KEYS = (
    "artifact_type",
    "authority_principal_id_sha256",
    "authorization_request_sha256",
    "canonical_payload_sha256",
    "revocation_epoch",
    "role",
    "schema",
    "signature_algorithm",
    "signature_sha256",
    "signature_valid_true",
    "trust_policy_sha256",
    "verification_key_version_sha256",
    "verified_at_utc",
)
_TRUST_POLICY_KEYS = (
    "authority_principal_id_sha256",
    "public_key_hex",
    "revocation_epoch",
    "role",
    "schema",
    "signature_algorithm",
    "verification_key_version_sha256",
)
_CONTROL_EVIDENCE_KEYS = (
    "assignment_sha256",
    "checked_at_utc",
    "cost_scope_sha256",
    "credential_scope_sha256",
    "kind",
    "namespace_id",
    "phase",
    "profile_sha256",
    "resource_scope_sha256",
    "revocation_epoch",
    "schema",
    "signature_algorithm",
    "signature_sha256",
    "simulation_run_id",
    "suite_id",
    "track_id",
    "trust_policy_sha256",
    "verification_key_version_sha256",
)


class OfflineAuthorityVerifier:
    """Verifies frozen bundle semantics and actively resolves every signed proof."""

    def __init__(
        self,
        contract: dict[str, Any],
        authority_schema: dict[str, Any],
    ) -> None:
        frozen_contract.validate_contract(copy.deepcopy(contract))
        frozen_contract.validate_authority_schema(copy.deepcopy(authority_schema))
        self._contract = copy.deepcopy(contract)
        self._authority_schema = copy.deepcopy(authority_schema)
        self._role_map = contract["authority_integrity"]["artifact_role_map"]

    def verify(
        self,
        bundle: dict[str, Any],
        evidence_store: OfflineEvidenceStore,
        private_capability: bytes,
        ledger: PrivateCapabilityControlLedgerDouble,
    ) -> VerifiedCapability:
        candidate = copy.deepcopy(bundle)
        frozen_contract._validate_authority_candidate(candidate, self._authority_schema)
        require(
            candidate["execution_capability_commitment"]["control_ledger_record_sha256"]
            == ledger.anchor_sha256,
            "E_LEDGER_ANCHOR",
            "bundle does not bind the supplied control ledger anchor",
        )
        require(
            ledger.adapter_id in ADAPTER_CATALOG,
            "E_ADAPTER_ID",
            "ledger adapter is not in frozen catalog",
        )
        spec = ADAPTER_CATALOG[ledger.adapter_id]
        require(spec.track_id == candidate["track_id"], "E_ADAPTER_TRACK", "adapter track mismatch")
        require(
            set(candidate["effective_allowed_operations"]).issubset(spec.allowed_operations),
            "E_ADAPTER_OPERATIONS",
            "capability operations exceed one adapter interface",
        )
        ledger.verify_secret(private_capability)
        expected_commitment = frozen_contract._private_capability_commitment(
            private_capability,
            candidate["execution_capability_commitment"],
        )
        require(
            expected_commitment
            == candidate["execution_capability_commitment"]["capability_commitment_sha256"],
            "E_CAPABILITY_COMMITMENT",
            "private capability commitment mismatch",
        )
        self._verify_scope_signatures(candidate, evidence_store)
        self._verify_control_evidence(candidate, evidence_store)
        capability = VerifiedCapability(candidate, ledger, private_capability)
        ledger.bind_capability_commitment(capability.commitment_sha256)
        return capability

    def _verify_scope_signatures(
        self,
        bundle: dict[str, Any],
        evidence_store: OfflineEvidenceStore,
    ) -> None:
        for slot, artifact_type in frozen_contract._AUTHORITY_ROLE_SLOTS:
            scope_receipt = bundle[slot]
            signature_receipt = evidence_store.resolve_document(
                scope_receipt["signature_receipt_sha256"],
                "E_SIGNATURE_RECEIPT",
                f"{slot} signature receipt",
            )
            exact_keys(
                signature_receipt,
                _SIGNATURE_RECEIPT_KEYS,
                "E_SIGNATURE_RECEIPT",
                f"{slot} signature receipt",
            )
            expected_role = self._role_map[artifact_type]
            expected = {
                "artifact_type": artifact_type,
                "authority_principal_id_sha256": scope_receipt[
                    "authority_principal_id_sha256"
                ],
                "authorization_request_sha256": scope_receipt[
                    "authorization_request_sha256"
                ],
                "canonical_payload_sha256": scope_receipt["canonical_payload_sha256"],
                "revocation_epoch": scope_receipt["revocation_epoch"],
                "role": expected_role,
                "trust_policy_sha256": scope_receipt["trust_policy_sha256"],
            }
            for key, value in expected.items():
                require(
                    signature_receipt[key] == value,
                    "E_SIGNATURE_BINDING",
                    f"{slot} signature {key} mismatch",
                )
            require(
                signature_receipt["schema"] == SIGNATURE_RECEIPT_SCHEMA,
                "E_SIGNATURE_SCHEMA",
                f"{slot} signature schema drift",
            )
            require(
                signature_receipt["signature_valid_true"] is True,
                "E_SIGNATURE_ASSERTION",
                f"{slot} signature assertion is not true",
            )
            verified_at = parse_utc(
                signature_receipt["verified_at_utc"],
                "E_SIGNATURE_TIME",
                f"{slot} verified_at",
            )
            require(
                parse_utc(scope_receipt["issued_at_utc"], "E_SIGNATURE_TIME", "issued_at")
                <= verified_at
                <= parse_utc(
                    bundle["currentness"]["checked_at_utc"],
                    "E_SIGNATURE_TIME",
                    "checked_at",
                ),
                "E_SIGNATURE_TIME",
                f"{slot} verification time is outside authority window",
            )
            self._verify_signature_material(
                signature_receipt,
                bytes.fromhex(scope_receipt["canonical_payload_sha256"]),
                evidence_store,
                expected_role,
                scope_receipt["authority_principal_id_sha256"],
            )

    def _verify_signature_material(
        self,
        receipt: dict[str, Any],
        message: bytes,
        evidence_store: OfflineEvidenceStore,
        expected_role: str,
        expected_principal: str,
    ) -> None:
        policy = evidence_store.resolve_document(
            receipt["trust_policy_sha256"],
            "E_TRUST_POLICY",
            "trust policy",
        )
        exact_keys(policy, _TRUST_POLICY_KEYS, "E_TRUST_POLICY", "trust policy")
        require(policy["schema"] == TRUST_POLICY_SCHEMA, "E_TRUST_POLICY", "policy schema drift")
        require(policy["role"] == expected_role, "E_TRUST_POLICY", "policy role mismatch")
        require(
            policy["authority_principal_id_sha256"] == expected_principal,
            "E_TRUST_POLICY",
            "policy principal mismatch",
        )
        for key in (
            "revocation_epoch",
            "signature_algorithm",
            "verification_key_version_sha256",
        ):
            require(policy[key] == receipt[key], "E_TRUST_POLICY", f"policy {key} mismatch")
        require(
            policy["signature_algorithm"] == "ED25519",
            "E_SIGNATURE_ALGORITHM",
            "only exact Ed25519 test policy is supported",
        )
        try:
            public_key = bytes.fromhex(policy["public_key_hex"])
        except (TypeError, ValueError) as exc:
            raise OfflineDoubleError("E_SIGNATURE_KEY: public key is not hex") from exc
        signature = evidence_store.resolve_signature(
            receipt["signature_sha256"], "E_SIGNATURE_BYTES", "signature bytes"
        )
        require(
            ed25519_verify(signature, message, public_key),
            "E_SIGNATURE_VERIFY",
            "active Ed25519 verification failed",
        )

    def _verify_control_evidence(
        self,
        bundle: dict[str, Any],
        evidence_store: OfflineEvidenceStore,
    ) -> None:
        expected_kinds = {
            "trusted_time_receipt_sha256": "TRUSTED_TIME",
            "row_currentness_receipt_sha256": "ROW_CURRENTNESS",
        }
        for reference_field, expected_kind in expected_kinds.items():
            document = evidence_store.resolve_document(
                bundle["currentness"][reference_field],
                "E_CONTROL_EVIDENCE",
                expected_kind,
            )
            exact_keys(
                document,
                _CONTROL_EVIDENCE_KEYS,
                "E_CONTROL_EVIDENCE",
                expected_kind,
            )
            require(document["schema"] == CONTROL_EVIDENCE_SCHEMA, "E_CONTROL_EVIDENCE", "schema drift")
            require(document["kind"] == expected_kind, "E_CONTROL_EVIDENCE", "kind mismatch")
            for key in (
                "assignment_sha256",
                "cost_scope_sha256",
                "credential_scope_sha256",
                "namespace_id",
                "phase",
                "profile_sha256",
                "resource_scope_sha256",
                "revocation_epoch",
                "simulation_run_id",
                "suite_id",
                "track_id",
            ):
                require(document[key] == bundle[key], "E_CONTROL_BINDING", f"{expected_kind} {key} mismatch")
            require(
                document["checked_at_utc"] == bundle["currentness"]["checked_at_utc"],
                "E_CONTROL_TIME",
                f"{expected_kind} checked_at mismatch",
            )
            parse_utc(document["checked_at_utc"], "E_CONTROL_TIME", "control checked_at")
            signed_payload = {
                key: copy.deepcopy(value)
                for key, value in document.items()
                if key != "signature_sha256"
            }
            pseudo_receipt = {
                "revocation_epoch": document["revocation_epoch"],
                "signature_algorithm": document["signature_algorithm"],
                "signature_sha256": document["signature_sha256"],
                "trust_policy_sha256": document["trust_policy_sha256"],
                "verification_key_version_sha256": document[
                    "verification_key_version_sha256"
                ],
            }
            self._verify_signature_material(
                pseudo_receipt,
                bytes.fromhex(sha256_value(signed_payload)),
                evidence_store,
                "CONTROL_PLANE_EVIDENCE",
                tag_hash("offline-control-plane-principal"),
            )


class ExperimentAdapterDouble:
    """One exact least-privilege interface with observation-only output."""

    def __init__(self, adapter_id: str) -> None:
        require(adapter_id in ADAPTER_CATALOG, "E_ADAPTER_ID", "unknown adapter double")
        self.spec = ADAPTER_CATALOG[adapter_id]
        self.credential_handle_commitment_sha256 = tag_hash(
            f"offline-opaque-credential-handle/{adapter_id}"
        )

    def invoke(
        self,
        capability: VerifiedCapability,
        operation: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        exact_keys(
            request,
            ("binding_sha256", "request_id_sha256"),
            "E_ADAPTER_REQUEST",
            "adapter request",
        )
        require(operation in self.spec.allowed_operations, "E_ADAPTER_OPERATION", "operation not allowed")
        require(operation not in self.spec.forbidden_operations, "E_ADAPTER_OPERATION", "operation forbidden")
        require(capability.track_id == self.spec.track_id, "E_ADAPTER_TRACK", "capability track mismatch")
        require(capability.adapter_id == self.spec.adapter_id, "E_ADAPTER_SCOPE", "capability adapter mismatch")
        capability._ledger.consume(capability, self.spec.adapter_id, operation)
        observation_fields = {
            field: tag_hash(
                f"offline-observation/{self.spec.adapter_id}/{operation}/{field}/"
                f"{capability.simulation_run_id}"
            )
            for field in self.spec.evidence_returns
        }
        return {
            "adapter_id": self.spec.adapter_id,
            "application_call_count": 0,
            "case_classification": None,
            "case_id": capability.case_id,
            "condition_output_authorized": False,
            "credential_class": self.spec.credential_class,
            "credential_handle_commitment_sha256": self.credential_handle_commitment_sha256,
            "credentials_accessed": False,
            "double_invocation_count": 1,
            "evidence_returns": observation_fields,
            "namespace_id": capability.namespace_id,
            "operation": operation,
            "output_permit_defined": False,
            "provider_called": False,
            "provider_processing_count": None,
            "receipt_is_execution_authority": False,
            "receipt_is_output_permit": False,
            "repetition_index": capability.repetition_index,
            "request_binding_sha256": request["binding_sha256"],
            "request_id_sha256": request["request_id_sha256"],
            "schema": ADAPTER_RECEIPT_SCHEMA,
            "side_effects_unlocked": "NONE",
            "simulation_run_id": capability.simulation_run_id,
            "track_id": capability.track_id,
            "wire_attempt_count": 0,
        }


class StopCapability:
    """Independent reductive-only capability for one assigned run."""

    __slots__ = ("_commitment_sha256", "_namespace_id", "_simulation_run_id")

    def __init__(self, simulation_run_id: str, namespace_id: str, label: str) -> None:
        self._simulation_run_id = simulation_run_id
        self._namespace_id = namespace_id
        self._commitment_sha256 = framed_hash(
            "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/"
            "runner/v1/offline-stop-capability",
            bytes.fromhex(simulation_run_id),
            bytes.fromhex(namespace_id),
            label.encode("utf-8"),
        )

    @property
    def commitment_sha256(self) -> str:
        return self._commitment_sha256

    @property
    def simulation_run_id(self) -> str:
        return self._simulation_run_id

    @property
    def namespace_id(self) -> str:
        return self._namespace_id

    def __getstate__(self) -> None:
        raise TypeError("stop capability is nonserializable")

    def __reduce__(self) -> None:
        raise TypeError("stop capability is nonserializable")


class StopControlDouble:
    """One independent STOP-only interface; no experiment operation is accepted."""

    def __init__(self, interface_id: str) -> None:
        require(interface_id in STOP_CONTROL_CATALOG, "E_STOP_INTERFACE", "unknown stop control")
        self.spec = STOP_CONTROL_CATALOG[interface_id]
        self.credential_handle_commitment_sha256 = tag_hash(
            f"offline-stop-credential-handle/{interface_id}"
        )

    def invoke(
        self,
        stop_capability: StopCapability,
        operations: tuple[str, ...],
        sequence_index: int,
        fail_closed: bool = False,
    ) -> dict[str, Any]:
        require(type(stop_capability) is StopCapability, "E_STOP_CAPABILITY", "invalid stop capability")
        require(operations, "E_STOP_OPERATION", "empty stop operation set")
        require(len(set(operations)) == len(operations), "E_STOP_OPERATION", "duplicate stop operation")
        require(
            set(operations).issubset(self.spec.allowed_operations),
            "E_STOP_OPERATION",
            "operation outside stop-only interface",
        )
        require(
            set(operations).isdisjoint(self.spec.forbidden_operations),
            "E_STOP_OPERATION",
            "forbidden stop operation",
        )
        if fail_closed:
            raise OfflineDoubleError(
                f"E_STOP_CONTROL_FAILURE: injected failure at {self.spec.interface_id}"
            )
        fields: dict[str, Any] = {}
        for field in self.spec.receipt_fields:
            if field == "ACTIVE_LEASE_COMMITMENTS_AFTER_STOP":
                fields[field] = 0
            elif field == "CONTROL_LEDGER_REVISION":
                fields[field] = sequence_index
            elif field == "CLEANUP_STATUS":
                fields[field] = "REDUCTIVE_CLEANUP_COMPLETE"
            else:
                fields[field] = tag_hash(
                    f"offline-stop/{self.spec.interface_id}/{field}/"
                    f"{stop_capability.simulation_run_id}/{sequence_index}"
                )
        return {
            "credential_class": self.spec.credential_class,
            "credential_handle_commitment_sha256": self.credential_handle_commitment_sha256,
            "credentials_accessed": False,
            "interface_id": self.spec.interface_id,
            "namespace_id": stop_capability.namespace_id,
            "operations": list(operations),
            "positive_execution_authority_added": False,
            "receipt_fields": fields,
            "receipt_is_execution_authority": False,
            "receipt_is_output_permit": False,
            "schema": STOP_DOUBLE_RECEIPT_SCHEMA,
            "sequence_index": sequence_index,
            "simulation_run_id": stop_capability.simulation_run_id,
            "stop_capability_commitment_sha256": stop_capability.commitment_sha256,
        }


_STOP_SEQUENCE = (
    (
        "CAPABILITY_FENCE_CONTROL",
        ("CAS_EXACT_RUN_CAPABILITY_TO_STOP_FENCED", "BLOCK_NEW_CALLS_FOR_EXACT_RUN"),
    ),
    (
        "DURABLE_EVIDENCE_RETENTION_CONTROL",
        ("PERSIST_CURRENT_ROW_DURABLE_STATE_AND_SAFE_EVIDENCE",),
    ),
    (
        "FAULT_DISARM_AND_EGRESS_ISOLATION_CONTROL",
        ("DISARM_EXACT_ASSIGNED_CUT", "ISOLATE_EXACT_ASSIGNED_RUN_EGRESS"),
    ),
    (
        "CREDENTIAL_BROKER_REVOCATION_CONTROL",
        ("REVOKE_EXACT_RUN_CREDENTIAL_LEASES", "CONFIRM_ZERO_ACTIVE_LEASE_COMMITMENTS"),
    ),
    (
        "DURABLE_EVIDENCE_RETENTION_CONTROL",
        ("CONFIRM_RETENTION_BINDINGS",),
    ),
    (
        "SCOPED_RESOURCE_CLEANUP_CONTROL",
        ("FREEZE_EXACT_ASSIGNED_RESOURCES", "REDUCTIVE_TEARDOWN_WITHIN_EXACT_CLEANUP_SCOPE"),
    ),
)


class StopCoordinatorDouble:
    """Runs the frozen absorbing STOP order and quarantines any control failure."""

    def __init__(
        self,
        controls: dict[str, StopControlDouble],
        contract: dict[str, Any],
    ) -> None:
        require(
            tuple(controls) == tuple(STOP_CONTROL_CATALOG),
            "E_STOP_CATALOG",
            "stop control set or order drift",
        )
        for interface_id, control in controls.items():
            require(
                type(control) is StopControlDouble and control.spec.interface_id == interface_id,
                "E_STOP_CATALOG",
                "stop control identity drift",
            )
        self._controls = controls
        self._trigger_map = copy.deepcopy(
            contract["start_stop_logic"]["stop"]["trigger_reason_role_map"]
        )

    def stop(
        self,
        ledger: PrivateCapabilityControlLedgerDouble,
        stop_capability: StopCapability,
        trigger: str,
        reason: str,
        role: str,
        fail_interface_id: str | None = None,
    ) -> dict[str, Any]:
        require(trigger in self._trigger_map, "E_STOP_TRIGGER", "unknown stop trigger")
        require(
            reason in self._trigger_map[trigger]["reasons"],
            "E_STOP_REASON",
            "stop reason does not belong to trigger",
        )
        require(
            role in self._trigger_map[trigger]["roles"],
            "E_STOP_ROLE",
            "stop role does not belong to trigger",
        )
        require(
            stop_capability.simulation_run_id == ledger._bindings["simulation_run_id"]
            and stop_capability.namespace_id == ledger._bindings["namespace_id"],
            "E_STOP_SCOPE",
            "stop capability assignment mismatch",
        )
        require(
            fail_interface_id is None or fail_interface_id in STOP_CONTROL_CATALOG,
            "E_STOP_FAILURE_TARGET",
            "unknown injected stop failure target",
        )
        operation_receipts: list[dict[str, Any]] = []
        ledger.fence_for_stop()
        try:
            for sequence_index, (interface_id, operations) in enumerate(_STOP_SEQUENCE, start=1):
                operation_receipts.append(
                    self._controls[interface_id].invoke(
                        stop_capability,
                        operations,
                        sequence_index,
                        fail_closed=(fail_interface_id == interface_id),
                    )
                )
        except OfflineDoubleError:
            ledger.finish_stop(False)
            return self._receipt(
                ledger,
                stop_capability,
                trigger,
                reason,
                role,
                operation_receipts,
                fail_interface_id,
                False,
            )
        ledger.finish_stop(True)
        return self._receipt(
            ledger,
            stop_capability,
            trigger,
            reason,
            role,
            operation_receipts,
            None,
            True,
        )

    @staticmethod
    def _receipt(
        ledger: PrivateCapabilityControlLedgerDouble,
        stop_capability: StopCapability,
        trigger: str,
        reason: str,
        role: str,
        operation_receipts: list[dict[str, Any]],
        failed_interface_id: str | None,
        success: bool,
    ) -> dict[str, Any]:
        return {
            "automatic_rerun_allowed": False,
            "capability_invalidated": True,
            "condition_output_authorized": False,
            "continuation_allowed": False,
            "control_plane_failure_ids": (
                []
                if failed_interface_id is None
                else [tag_hash(f"offline-stop-failure/{failed_interface_id}")]
            ),
            "credentials_accessed": False,
            "evidence_preserved": True,
            "failed_interface_id": failed_interface_id,
            "manual_escalation_required": not success,
            "namespace_id": stop_capability.namespace_id,
            "new_calls_blocked": True,
            "operation_receipts": copy.deepcopy(operation_receipts),
            "provider_called": False,
            "receipt_is_execution_authority": False,
            "receipt_is_output_permit": False,
            "retained_row_preserved": True,
            "schema": STOP_DOUBLE_RECEIPT_SCHEMA,
            "side_effects_unlocked": "NONE",
            "simulation_run_id": stop_capability.simulation_run_id,
            "stop_capability_commitment_sha256": stop_capability.commitment_sha256,
            "stop_lifecycle_state": (
                "STOP_ABSORBING_COMPLETE" if success else "STOP_FAILED_QUARANTINED"
            ),
            "stop_reason": reason,
            "stop_trigger": trigger,
            "stop_trigger_role": role,
            "terminal": True,
            "unresolved_ambiguity_ids": [],
            "control_ledger_revision": ledger.revision,
        }


def _assert_catalogs_match_contract(contract: dict[str, Any]) -> None:
    expected_adapter_ids: list[str] = []
    for section_name, track_id in (
        ("managed", MANAGED_TRACK),
        ("self_hosted", SELF_HOSTED_TRACK),
    ):
        section = contract["adapter_interfaces"][section_name]
        require(
            section["adapter_count"] == len(section["adapters"]),
            "E_CONTRACT_ADAPTER_COUNT",
            f"{section_name} adapter count drift",
        )
        for raw in section["adapters"]:
            adapter_id = raw["adapter_id"]
            expected_adapter_ids.append(adapter_id)
            require(adapter_id in ADAPTER_CATALOG, "E_CONTRACT_ADAPTER", "missing adapter double")
            spec = ADAPTER_CATALOG[adapter_id]
            require(spec.track_id == track_id, "E_CONTRACT_ADAPTER", "adapter track drift")
            require(spec.credential_class == raw["credential_class"], "E_CONTRACT_ADAPTER", "credential class drift")
            require(spec.allowed_operations == tuple(raw["allowed_operations"]), "E_CONTRACT_ADAPTER", "allowed operation drift")
            require(spec.forbidden_operations == tuple(raw["forbidden_operations"]), "E_CONTRACT_ADAPTER", "forbidden operation drift")
            require(spec.evidence_returns == tuple(raw["evidence_returns"]), "E_CONTRACT_ADAPTER", "evidence return drift")
    require(
        tuple(expected_adapter_ids) == tuple(ADAPTER_CATALOG),
        "E_CONTRACT_ADAPTER",
        "adapter identity/order drift",
    )

    raw_controls = contract["stop_control_plane"]["interfaces"]
    require(len(raw_controls) == 5, "E_CONTRACT_STOP", "stop control count drift")
    require(
        tuple(raw["interface_id"] for raw in raw_controls) == tuple(STOP_CONTROL_CATALOG),
        "E_CONTRACT_STOP",
        "stop control identity/order drift",
    )
    for raw in raw_controls:
        spec = STOP_CONTROL_CATALOG[raw["interface_id"]]
        require(spec.credential_class == raw["credential_class"], "E_CONTRACT_STOP", "stop credential drift")
        require(spec.allowed_operations == tuple(raw["allowed_operations"]), "E_CONTRACT_STOP", "stop allowed operation drift")
        require(spec.forbidden_operations == tuple(raw["forbidden_operations"]), "E_CONTRACT_STOP", "stop forbidden operation drift")
        require(spec.receipt_fields == tuple(raw["receipt_fields"]), "E_CONTRACT_STOP", "stop receipt field drift")

    experiment_credentials = {spec.credential_class for spec in ADAPTER_CATALOG.values()}
    stop_credentials = {spec.credential_class for spec in STOP_CONTROL_CATALOG.values()}
    require(len(experiment_credentials) == 9, "E_CREDENTIAL_ISOLATION", "experiment credential reuse")
    require(len(stop_credentials) == 5, "E_CREDENTIAL_ISOLATION", "stop credential reuse")
    require(
        experiment_credentials.isdisjoint(stop_credentials),
        "E_CREDENTIAL_ISOLATION",
        "stop credential reused for experiment",
    )


def _test_seed(label: str) -> bytes:
    return bytes.fromhex(tag_hash(f"offline-test-ed25519-seed/{label}"))


def _add_trust_policy(
    store: OfflineEvidenceStore,
    role: str,
    principal_sha256: str,
    revocation_epoch: int,
    seed: bytes,
) -> tuple[str, str]:
    public_key = ed25519_public_key(seed)
    key_version_sha256 = tag_hash(f"offline-key-version/{role}/{public_key.hex()}")
    policy = {
        "authority_principal_id_sha256": principal_sha256,
        "public_key_hex": public_key.hex(),
        "revocation_epoch": revocation_epoch,
        "role": role,
        "schema": TRUST_POLICY_SCHEMA,
        "signature_algorithm": "ED25519",
        "verification_key_version_sha256": key_version_sha256,
    }
    return store.add_document(policy), key_version_sha256


def _authorization_request_sha256(receipt: dict[str, Any]) -> str:
    request = {
        "artifact_type": receipt["artifact_type"],
        "assignment_sha256": receipt["assignment_sha256"],
        "authority_principal_id_sha256": receipt["authority_principal_id_sha256"],
        "cleanup_policy_sha256": receipt["cleanup_policy_sha256"],
        "cost_scope_sha256": receipt["cost_scope_sha256"],
        "credential_scope_sha256": receipt["credential_scope_sha256"],
        "namespace_id": receipt["namespace_id"],
        "nonce_sha256": receipt["nonce_sha256"],
        "phase": receipt["phase"],
        "profile_sha256": receipt["profile_sha256"],
        "resource_scope_sha256": receipt["resource_scope_sha256"],
        "revocation_epoch": receipt["revocation_epoch"],
        "simulation_run_id": receipt["simulation_run_id"],
        "suite_id": receipt["suite_id"],
        "track_id": receipt["track_id"],
    }
    return framed_hash(
        frozen_contract.AUTHORIZATION_REQUEST_DOMAIN,
        canonical_bytes(request),
    )


def _sign_scope_receipt(
    scope_receipt: dict[str, Any],
    role: str,
    store: OfflineEvidenceStore,
    seed: bytes,
) -> None:
    trust_policy_sha256, key_version_sha256 = _add_trust_policy(
        store,
        role,
        scope_receipt["authority_principal_id_sha256"],
        scope_receipt["revocation_epoch"],
        seed,
    )
    scope_receipt["trust_policy_sha256"] = trust_policy_sha256
    scope_receipt["authorization_request_sha256"] = _authorization_request_sha256(
        scope_receipt
    )
    scope_receipt["canonical_payload_sha256"] = frozen_contract._scope_payload_sha256(
        scope_receipt
    )
    signature = ed25519_sign(
        bytes.fromhex(scope_receipt["canonical_payload_sha256"]), seed
    )
    signature_sha256 = store.add_signature(signature)
    signature_receipt = {
        "artifact_type": scope_receipt["artifact_type"],
        "authority_principal_id_sha256": scope_receipt[
            "authority_principal_id_sha256"
        ],
        "authorization_request_sha256": scope_receipt[
            "authorization_request_sha256"
        ],
        "canonical_payload_sha256": scope_receipt["canonical_payload_sha256"],
        "revocation_epoch": scope_receipt["revocation_epoch"],
        "role": role,
        "schema": SIGNATURE_RECEIPT_SCHEMA,
        "signature_algorithm": "ED25519",
        "signature_sha256": signature_sha256,
        "signature_valid_true": True,
        "trust_policy_sha256": trust_policy_sha256,
        "verification_key_version_sha256": key_version_sha256,
        "verified_at_utc": "2026-07-16T20:00:00Z",
    }
    scope_receipt["signature_receipt_sha256"] = store.add_document(
        signature_receipt
    )
    scope_receipt["receipt_id"] = frozen_contract._scope_receipt_id(scope_receipt)


def _add_control_evidence(
    kind: str,
    bundle: dict[str, Any],
    store: OfflineEvidenceStore,
) -> str:
    principal_sha256 = tag_hash("offline-control-plane-principal")
    seed = _test_seed("control-plane")
    trust_policy_sha256, key_version_sha256 = _add_trust_policy(
        store,
        "CONTROL_PLANE_EVIDENCE",
        principal_sha256,
        bundle["revocation_epoch"],
        seed,
    )
    document = {
        "assignment_sha256": bundle["assignment_sha256"],
        "checked_at_utc": bundle["currentness"]["checked_at_utc"],
        "cost_scope_sha256": bundle["cost_scope_sha256"],
        "credential_scope_sha256": bundle["credential_scope_sha256"],
        "kind": kind,
        "namespace_id": bundle["namespace_id"],
        "phase": bundle["phase"],
        "profile_sha256": bundle["profile_sha256"],
        "resource_scope_sha256": bundle["resource_scope_sha256"],
        "revocation_epoch": bundle["revocation_epoch"],
        "schema": CONTROL_EVIDENCE_SCHEMA,
        "signature_algorithm": "ED25519",
        "signature_sha256": "0" * 64,
        "simulation_run_id": bundle["simulation_run_id"],
        "suite_id": bundle["suite_id"],
        "track_id": bundle["track_id"],
        "trust_policy_sha256": trust_policy_sha256,
        "verification_key_version_sha256": key_version_sha256,
    }
    signed_payload = {
        key: copy.deepcopy(value)
        for key, value in document.items()
        if key != "signature_sha256"
    }
    signature = ed25519_sign(bytes.fromhex(sha256_value(signed_payload)), seed)
    document["signature_sha256"] = store.add_signature(signature)
    return store.add_document(document)


def build_synthetic_authority_fixture(
    contract: dict[str, Any],
    adapter_id: str,
    ordinal: int,
) -> tuple[
    dict[str, Any],
    OfflineEvidenceStore,
    bytes,
    PrivateCapabilityControlLedgerDouble,
]:
    """Build one deterministic, fully signed, exact-run offline authority fixture."""

    _assert_catalogs_match_contract(contract)
    require(adapter_id in ADAPTER_CATALOG, "E_ADAPTER_ID", "unknown adapter fixture")
    require(1 <= ordinal <= 9, "E_FIXTURE_ORDINAL", "fixture ordinal out of range")
    spec = ADAPTER_CATALOG[adapter_id]
    case_id = "M00" if spec.track_id == MANAGED_TRACK else "S00"
    repetition_index = ordinal
    operation = spec.allowed_operations[0]
    assignment_sha256, simulation_run_id, namespace_id = (
        frozen_contract._assignment_lineage(
            spec.track_id,
            case_id,
            repetition_index,
        )
    )
    private_capability = bytes.fromhex(
        tag_hash(f"offline-private-capability/{adapter_id}/{ordinal}")
    )
    bundle = frozen_contract._authority_kat()
    bindings = {
        "adapter_build_sha256": tag_hash(f"offline-adapter-build/{adapter_id}"),
        "adapter_set_manifest_sha256": tag_hash("offline-adapter-set-manifest/v1"),
        "assignment_sha256": assignment_sha256,
        "cleanup_policy_sha256": tag_hash("offline-cleanup-policy/v1"),
        "configuration_sha256": frozen_contract.OFFLINE_CONFIGURATION_SHA256,
        "contract_sha256": frozen_contract.ADAPTER_CONTRACT_SHA256,
        "cost_scope_sha256": tag_hash("offline-zero-cost-scope/v1"),
        "credential_scope_sha256": tag_hash(
            f"offline-opaque-credential-scope/{adapter_id}"
        ),
        "namespace_id": namespace_id,
        "offline_harness_manifest_sha256": frozen_contract.OFFLINE_HARNESS_MANIFEST_SHA256,
        "phase": "EXPERIMENT_EXECUTION_GRANT",
        "profile_sha256": tag_hash(f"offline-profile/{spec.track_id}"),
        "resource_scope_sha256": tag_hash("offline-zero-resource-scope/v1"),
        "retention_policy_sha256": tag_hash("offline-retention-policy/v1"),
        "revocation_epoch": 7,
        "runner_build_sha256": tag_hash("offline-runner-build/v1"),
        "schedule_sha256": frozen_contract.OFFLINE_SCHEDULE_SHA256,
        "simulation_run_id": simulation_run_id,
        "stop_control_plane_manifest_sha256": tag_hash(
            "offline-stop-control-plane-manifest/v1"
        ),
        "suite_id": frozen_contract.OFFLINE_SUITE_ID,
        "track_id": spec.track_id,
    }
    for key, value in bindings.items():
        if key in bundle:
            bundle[key] = copy.deepcopy(value)
        if key in bundle["authority_intersection"]:
            bundle["authority_intersection"][key] = copy.deepcopy(value)
        if key in bundle["execution_capability_commitment"]:
            bundle["execution_capability_commitment"][key] = copy.deepcopy(value)
        for slot, _ in frozen_contract._AUTHORITY_ROLE_SLOTS:
            if key in bundle[slot]:
                bundle[slot][key] = copy.deepcopy(value)

    bundle["case_id"] = case_id
    bundle["repetition_index"] = repetition_index
    bundle["effective_allowed_operations"] = [operation]
    intersection = bundle["authority_intersection"]
    intersection["effective_allowed_case_ids"] = [case_id]
    intersection["effective_allowed_operations"] = [operation]
    intersection["effective_allowed_repetition_indices"] = [repetition_index]
    intersection["field_level_intersection_sha256"] = (
        frozen_contract._authority_intersection_sha256(intersection)
    )
    bundle["field_level_intersection_sha256"] = intersection[
        "field_level_intersection_sha256"
    ]
    capability_commitment = bundle["execution_capability_commitment"]
    capability_commitment["case_id"] = case_id
    capability_commitment["repetition_index"] = repetition_index
    capability_commitment["effective_allowed_operations"] = [operation]
    capability_commitment["field_level_intersection_sha256"] = intersection[
        "field_level_intersection_sha256"
    ]
    capability_commitment["channel_binding_sha256"] = tag_hash(
        f"offline-channel/{adapter_id}/{simulation_run_id}"
    )

    store = OfflineEvidenceStore()
    for role_index, (slot, artifact_type) in enumerate(
        frozen_contract._AUTHORITY_ROLE_SLOTS,
        start=1,
    ):
        scope_receipt = bundle[slot]
        scope_receipt["allowed_case_ids"] = [case_id]
        scope_receipt["allowed_repetition_indices"] = [repetition_index]
        scope_receipt["allowed_operations"] = [
            "BLOCK_NEW_CALLS_FOR_EXACT_RUN"
            if artifact_type == "EMERGENCY_STOP_AUTHORITY_RECEIPT"
            else operation
        ]
        scope_receipt["authority_principal_id_sha256"] = tag_hash(
            f"offline-principal/{adapter_id}/{artifact_type}"
        )
        scope_receipt["nonce_sha256"] = tag_hash(
            f"offline-nonce/{adapter_id}/{artifact_type}/{ordinal}"
        )
        scope_receipt["issued_at_utc"] = "2026-07-16T19:00:00Z"
        scope_receipt["not_before_utc"] = "2026-07-16T19:30:00Z"
        scope_receipt["expires_at_utc"] = "2026-07-16T21:00:00Z"
        role = contract["authority_integrity"]["artifact_role_map"][artifact_type]
        _sign_scope_receipt(
            scope_receipt,
            role,
            store,
            _test_seed(f"scope-role/{role_index}/{role}"),
        )

    ledger_bindings = {
        "adapter_id": adapter_id,
        "assignment_sha256": assignment_sha256,
        "case_id": case_id,
        "effective_allowed_operations": [operation],
        "field_level_intersection_sha256": intersection[
            "field_level_intersection_sha256"
        ],
        "namespace_id": namespace_id,
        "phase": bundle["phase"],
        "repetition_index": repetition_index,
        "simulation_run_id": simulation_run_id,
        "suite_id": bundle["suite_id"],
        "track_id": spec.track_id,
    }
    ledger = PrivateCapabilityControlLedgerDouble(ledger_bindings, private_capability)
    capability_commitment["control_ledger_record_sha256"] = ledger.anchor_sha256
    capability_commitment["capability_commitment_sha256"] = (
        frozen_contract._private_capability_commitment(
            private_capability,
            capability_commitment,
        )
    )
    bundle["currentness"] = {
        "checked_at_utc": "2026-07-16T20:00:00Z",
        "cost_budget_reserved": True,
        "credential_lease_current": True,
        "profile_current": True,
        "resource_budget_reserved": True,
        "revocation_epoch": 7,
        "row_currentness_receipt_sha256": "0" * 64,
        "trusted_time_receipt_sha256": "0" * 64,
    }
    bundle["currentness"]["trusted_time_receipt_sha256"] = _add_control_evidence(
        "TRUSTED_TIME", bundle, store
    )
    bundle["currentness"]["row_currentness_receipt_sha256"] = _add_control_evidence(
        "ROW_CURRENTNESS", bundle, store
    )
    bundle["bundle_id"] = frozen_contract._authority_bundle_id(bundle)
    return bundle, store, private_capability, ledger


def _expect_rejection(action: Any, code: str) -> None:
    try:
        action()
    except OfflineDoubleError:
        return
    raise OfflineDoubleError(f"{code}: expected fail-closed rejection did not occur")


def _validate_adapter_receipt(receipt: dict[str, Any], spec: AdapterSpec) -> None:
    expected_keys = (
        "adapter_id",
        "application_call_count",
        "case_classification",
        "case_id",
        "condition_output_authorized",
        "credential_class",
        "credential_handle_commitment_sha256",
        "credentials_accessed",
        "double_invocation_count",
        "evidence_returns",
        "namespace_id",
        "operation",
        "output_permit_defined",
        "provider_called",
        "provider_processing_count",
        "receipt_is_execution_authority",
        "receipt_is_output_permit",
        "repetition_index",
        "request_binding_sha256",
        "request_id_sha256",
        "schema",
        "side_effects_unlocked",
        "simulation_run_id",
        "track_id",
        "wire_attempt_count",
    )
    exact_keys(receipt, expected_keys, "E_ADAPTER_RECEIPT", "adapter receipt")
    require(receipt["schema"] == ADAPTER_RECEIPT_SCHEMA, "E_ADAPTER_RECEIPT", "schema drift")
    require(receipt["adapter_id"] == spec.adapter_id, "E_ADAPTER_RECEIPT", "adapter id drift")
    require(receipt["track_id"] == spec.track_id, "E_ADAPTER_RECEIPT", "track drift")
    require(receipt["credential_class"] == spec.credential_class, "E_ADAPTER_RECEIPT", "credential drift")
    require(receipt["operation"] in spec.allowed_operations, "E_ADAPTER_RECEIPT", "operation drift")
    require(set(receipt["evidence_returns"]) == set(spec.evidence_returns), "E_ADAPTER_RECEIPT", "evidence fields drift")
    require(receipt["double_invocation_count"] == 1, "E_ADAPTER_RECEIPT", "double call count drift")
    require(receipt["application_call_count"] == 0, "E_ADAPTER_RECEIPT", "application call overclaim")
    require(receipt["wire_attempt_count"] == 0, "E_ADAPTER_RECEIPT", "wire attempt overclaim")
    require(receipt["provider_processing_count"] is None, "E_ADAPTER_RECEIPT", "provider processing overclaim")
    require(receipt["case_classification"] is None, "E_ADAPTER_RECEIPT", "adapter classified case")
    for field in (
        "condition_output_authorized",
        "credentials_accessed",
        "output_permit_defined",
        "provider_called",
        "receipt_is_execution_authority",
        "receipt_is_output_permit",
    ):
        require(receipt[field] is False, "E_ADAPTER_RECEIPT", f"{field} boundary drift")
    require(receipt["side_effects_unlocked"] == "NONE", "E_ADAPTER_RECEIPT", "side effect drift")


def _validate_stop_double_receipt(
    receipt: dict[str, Any],
    success: bool,
    expected_failure: str | None,
) -> None:
    require(receipt["schema"] == STOP_DOUBLE_RECEIPT_SCHEMA, "E_STOP_RECEIPT", "schema drift")
    require(receipt["terminal"] is True, "E_STOP_RECEIPT", "stop receipt not terminal")
    require(receipt["capability_invalidated"] is True, "E_STOP_RECEIPT", "capability not invalidated")
    require(receipt["new_calls_blocked"] is True, "E_STOP_RECEIPT", "new calls not blocked")
    require(receipt["retained_row_preserved"] is True, "E_STOP_RECEIPT", "row not preserved")
    require(receipt["evidence_preserved"] is True, "E_STOP_RECEIPT", "evidence not preserved")
    for field in (
        "automatic_rerun_allowed",
        "condition_output_authorized",
        "continuation_allowed",
        "credentials_accessed",
        "provider_called",
        "receipt_is_execution_authority",
        "receipt_is_output_permit",
    ):
        require(receipt[field] is False, "E_STOP_RECEIPT", f"{field} boundary drift")
    require(receipt["side_effects_unlocked"] == "NONE", "E_STOP_RECEIPT", "side effect drift")
    if success:
        require(
            receipt["stop_lifecycle_state"] == "STOP_ABSORBING_COMPLETE",
            "E_STOP_RECEIPT",
            "successful stop state drift",
        )
        require(receipt["failed_interface_id"] is None, "E_STOP_RECEIPT", "success has failure")
        require(receipt["control_plane_failure_ids"] == [], "E_STOP_RECEIPT", "success has failure id")
        require(receipt["manual_escalation_required"] is False, "E_STOP_RECEIPT", "success escalates")
        require(len(receipt["operation_receipts"]) == 6, "E_STOP_RECEIPT", "stop sequence length drift")
        require(
            tuple(item["interface_id"] for item in receipt["operation_receipts"])
            == tuple(item[0] for item in _STOP_SEQUENCE),
            "E_STOP_RECEIPT",
            "stop operation order drift",
        )
    else:
        require(
            receipt["stop_lifecycle_state"] == "STOP_FAILED_QUARANTINED",
            "E_STOP_RECEIPT",
            "failed stop did not quarantine",
        )
        require(receipt["failed_interface_id"] == expected_failure, "E_STOP_RECEIPT", "failure identity drift")
        require(len(receipt["control_plane_failure_ids"]) == 1, "E_STOP_RECEIPT", "failure id missing")
        require(receipt["manual_escalation_required"] is True, "E_STOP_RECEIPT", "failed stop did not escalate")


def run_conformance(
    contract: dict[str, Any],
    authority_schema: dict[str, Any],
    stop_schema: dict[str, Any],
) -> dict[str, Any]:
    """Exercise every offline double and return a deterministic non-authorizing receipt."""

    frozen_contract.validate_contract(copy.deepcopy(contract))
    frozen_contract.validate_authority_schema(copy.deepcopy(authority_schema))
    frozen_contract.validate_stop_schema(copy.deepcopy(stop_schema))
    _assert_catalogs_match_contract(contract)
    verifier = OfflineAuthorityVerifier(contract, authority_schema)

    adapter_receipts: list[dict[str, Any]] = []
    authority_bundle_ids: list[str] = []
    ledgers: list[PrivateCapabilityControlLedgerDouble] = []
    capabilities: list[VerifiedCapability] = []
    duplicate_start_rejections = 0
    forbidden_rejections = 0
    cross_scope_rejections = 0
    duplicate_rejections = 0

    adapter_ids = tuple(ADAPTER_CATALOG)
    for ordinal, adapter_id in enumerate(adapter_ids, start=1):
        bundle, store, private_capability, ledger = build_synthetic_authority_fixture(
            contract,
            adapter_id,
            ordinal,
        )
        capability = verifier.verify(bundle, store, private_capability, ledger)
        authority_bundle_ids.append(bundle["bundle_id"])
        ledger.start(capability)
        _expect_rejection(
            lambda ledger=ledger, capability=capability: ledger.start(capability),
            "E_SELF_TEST_START",
        )
        duplicate_start_rejections += 1
        adapter = ExperimentAdapterDouble(adapter_id)
        spec = ADAPTER_CATALOG[adapter_id]
        request = {
            "binding_sha256": tag_hash(
                f"offline-request-binding/{adapter_id}/{capability.simulation_run_id}"
            ),
            "request_id_sha256": tag_hash(
                f"offline-request/{adapter_id}/{capability.simulation_run_id}"
            ),
        }
        _expect_rejection(
            lambda adapter=adapter, capability=capability, spec=spec, request=request: adapter.invoke(
                capability,
                spec.forbidden_operations[0],
                request,
            ),
            "E_SELF_TEST_FORBIDDEN",
        )
        forbidden_rejections += 1
        other_adapter_id = adapter_ids[ordinal % len(adapter_ids)]
        other_adapter = ExperimentAdapterDouble(other_adapter_id)
        _expect_rejection(
            lambda other_adapter=other_adapter, capability=capability, request=request: other_adapter.invoke(
                capability,
                other_adapter.spec.allowed_operations[0],
                request,
            ),
            "E_SELF_TEST_CROSS_SCOPE",
        )
        cross_scope_rejections += 1
        receipt = adapter.invoke(capability, spec.allowed_operations[0], request)
        _validate_adapter_receipt(receipt, spec)
        adapter_receipts.append(receipt)
        _expect_rejection(
            lambda adapter=adapter, capability=capability, spec=spec, request=request: adapter.invoke(
                capability,
                spec.allowed_operations[0],
                request,
            ),
            "E_SELF_TEST_DUPLICATE",
        )
        duplicate_rejections += 1
        ledgers.append(ledger)
        capabilities.append(capability)

    controls = {
        interface_id: StopControlDouble(interface_id)
        for interface_id in STOP_CONTROL_CATALOG
    }
    coordinator = StopCoordinatorDouble(controls, contract)
    stop_trigger = "OWNER_CUSTODIAN_OR_EMERGENCY_OPERATOR_STOP"
    stop_reason = "OPERATOR_STOP"
    stop_role = "OWNER"
    success_ledger = ledgers[0]
    success_stop_capability = StopCapability(
        capabilities[0].simulation_run_id,
        capabilities[0].namespace_id,
        "absorbing-success",
    )
    successful_stop = coordinator.stop(
        success_ledger,
        success_stop_capability,
        stop_trigger,
        stop_reason,
        stop_role,
    )
    _validate_stop_double_receipt(successful_stop, True, None)

    failed_stops: list[dict[str, Any]] = []
    for failure_index, interface_id in enumerate(STOP_CONTROL_CATALOG, start=1):
        failure_ledger = ledgers[1].clone_started_for_stop_test()
        failure_stop_capability = StopCapability(
            capabilities[1].simulation_run_id,
            capabilities[1].namespace_id,
            f"quarantine-{failure_index}-{interface_id}",
        )
        failed = coordinator.stop(
            failure_ledger,
            failure_stop_capability,
            stop_trigger,
            stop_reason,
            stop_role,
            fail_interface_id=interface_id,
        )
        _validate_stop_double_receipt(failed, False, interface_id)
        failed_stops.append(failed)

    receipt: dict[str, Any] = {
        "adapter_calls": len(adapter_receipts),
        "adapter_cross_scope_rejections": cross_scope_rejections,
        "adapter_duplicate_rejections": duplicate_rejections,
        "adapter_forbidden_rejections": forbidden_rejections,
        "adapter_ids": list(ADAPTER_CATALOG),
        "adapter_receipts_sha256": sha256_value(adapter_receipts),
        "authority_bundle_ids_sha256": sha256_value(authority_bundle_ids),
        "authority_bundles_verified": len(authority_bundle_ids),
        "condition_outputs": 0,
        "content_sha256": "0" * 64,
        "control_evidence_receipts_verified": 2 * len(authority_bundle_ids),
        "control_ledger_duplicate_start_rejections": duplicate_start_rejections,
        "control_ledger_start_cas": len(authority_bundle_ids),
        "credentials_accessed": 0,
        "date": "2026-07-16",
        "decision": DECISION,
        "experiment_rows": 0,
        "next_unit": NEXT_UNIT,
        "output_permits": 0,
        "paid_resources_provisioned": 0,
        "private_capability_commitments_verified": len(authority_bundle_ids),
        "provider_calls": 0,
        "receipt_is_execution_authority": False,
        "receipt_is_output_permit": False,
        "runtime_authority": False,
        "runtime_rows": 0,
        "schema": CONFORMANCE_SCHEMA,
        "scope_signature_receipts_verified": 5 * len(authority_bundle_ids),
        "side_effects_unlocked": "NONE",
        "status": STATUS,
        "stop_control_ids": list(STOP_CONTROL_CATALOG),
        "stop_control_operation_receipts": len(successful_stop["operation_receipts"]),
        "stop_receipts_sha256": sha256_value([successful_stop, *failed_stops]),
        "stop_sequences_absorbing_complete": 1,
        "stop_sequences_failed_quarantined": len(failed_stops),
        "wire_attempts": 0,
    }
    receipt["content_sha256"] = sha256_value(
        {key: copy.deepcopy(value) for key, value in receipt.items() if key != "content_sha256"}
    )
    return receipt


TSV_FIELDS = (
    "schema",
    "status",
    "decision",
    "authority_bundles_verified",
    "scope_signature_receipts_verified",
    "control_evidence_receipts_verified",
    "private_capability_commitments_verified",
    "control_ledger_start_cas",
    "adapter_calls",
    "adapter_forbidden_rejections",
    "adapter_cross_scope_rejections",
    "adapter_duplicate_rejections",
    "stop_sequences_absorbing_complete",
    "stop_sequences_failed_quarantined",
    "stop_control_operation_receipts",
    "provider_calls",
    "wire_attempts",
    "credentials_accessed",
    "paid_resources_provisioned",
    "runtime_rows",
    "experiment_rows",
    "condition_outputs",
    "output_permits",
    "side_effects_unlocked",
    "receipt_is_execution_authority",
    "receipt_is_output_permit",
    "runtime_authority",
    "content_sha256",
    "next_unit",
)


def render_tsv(receipt: dict[str, Any]) -> str:
    rows = []
    for field in TSV_FIELDS:
        value = receipt[field]
        if type(value) is bool:
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        rows.append(f"{field}\t{rendered}")
    return "\n".join(rows) + "\n"
