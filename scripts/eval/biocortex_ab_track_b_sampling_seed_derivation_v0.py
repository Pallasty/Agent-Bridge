#!/usr/bin/env python3
"""Track B sampling-seed derivation with an explicit anti-shopping boundary.

The pure algorithm derives a 32-byte seed from externally supplied entropy and
public trial/frame bindings.  It cannot prove that entropy was unpredictable,
that a frame receipt used O_EXCL, or that timing preceded condition output;
those remain later custody receipts.  All derivation inputs are public
commitments, so the seed is intentionally publicly recomputable after entropy
publication; this source makes no seed-secrecy claim.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any


REQUEST_SCHEMA = "agent_bridge.biocortex_ab_track_b_sampling_seed_request.v0"
RESULT_SCHEMA = "agent_bridge.biocortex_ab_track_b_sampling_seed_result.v0"
RESULT_STATUS = "SOURCE_DERIVATION_ONLY_NOT_ENTROPY_OR_TIMING_RECEIPT"
SEED_DOMAIN = "agent-bridge/track-b/sample/v1"
SEED_MESSAGE_PROFILE = (
    "domain_utf8_NUL_contract_sha256_ascii_NUL_trial_id_utf8_NUL_"
    "eligible_frame_sha256_ascii_NUL_external_entropy_sha256_ascii"
)
ENTROPY_BYTES = 32

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
REQUEST_FIELDS = {
    "contract_sha256",
    "eligible_frame_manifest_sha256",
    "external_entropy_sha256",
    "schema",
    "trial_id",
}


class SamplingSeedError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def fail(code: str, message: str) -> None:
    raise SamplingSeedError(code, message)


@dataclass(frozen=True)
class SeedDerivation:
    """Seed bytes plus a public, independently reproducible derivation record.

    ``repr`` omits the bytes to avoid redundant accidental serialization.  It
    is output hygiene, not a confidentiality boundary: ``public_result`` has
    every input needed to recompute the bytes.
    """

    seed_bytes: bytes = field(repr=False)
    public_result: dict[str, Any]


def _require_sha(value: Any, label: str) -> str:
    if type(value) is not str or SHA_RE.fullmatch(value) is None:
        fail("SHA256", f"{label} must be 64 lowercase hexadecimal characters")
    return value


def _require_label(value: Any, label: str) -> str:
    if type(value) is not str or LABEL_RE.fullmatch(value) is None:
        fail("LABEL", f"{label} is outside the frozen label profile")
    return value


def _derive_with_domain(
    external_entropy_sha256: str,
    domain: str,
    contract_sha256: str,
    trial_id: str,
    frame_sha256: str,
) -> tuple[bytes, bytes]:
    message = b"\0".join(
        (
            domain.encode("utf-8"),
            contract_sha256.encode("ascii"),
            trial_id.encode("utf-8"),
            frame_sha256.encode("ascii"),
            external_entropy_sha256.encode("ascii"),
        )
    )
    return hashlib.sha256(message).digest(), message


def derive_sampling_seed(request: Any) -> SeedDerivation:
    if type(request) is not dict or set(request) != REQUEST_FIELDS:
        fail("REQUEST_KEYS", "seed request field set differs from the frozen profile")
    if request["schema"] != REQUEST_SCHEMA:
        fail("REQUEST_SCHEMA", "seed request schema drift")
    contract_sha256 = _require_sha(request["contract_sha256"], "contract_sha256")
    frame_sha256 = _require_sha(
        request["eligible_frame_manifest_sha256"],
        "eligible_frame_manifest_sha256",
    )
    trial_id = _require_label(request["trial_id"], "trial_id")
    entropy_sha256 = _require_sha(
        request["external_entropy_sha256"], "external_entropy_sha256"
    )

    seed, _message = _derive_with_domain(
        entropy_sha256,
        SEED_DOMAIN,
        contract_sha256,
        trial_id,
        frame_sha256,
    )
    return SeedDerivation(
        seed_bytes=seed,
        public_result={
            "schema": RESULT_SCHEMA,
            "status": RESULT_STATUS,
            "contract_sha256": contract_sha256,
            "trial_id": trial_id,
            "eligible_frame_manifest_sha256": frame_sha256,
            "external_entropy_sha256": entropy_sha256,
            "sampling_seed_sha256": hashlib.sha256(seed).hexdigest(),
            "seed_derivation_domain": SEED_DOMAIN,
            "seed_derivation_message_profile": SEED_MESSAGE_PROFILE,
            "derived_seed_bytes": ENTROPY_BYTES,
            "raw_entropy_consumed": False,
            "derived_seed_directly_serialized": False,
            "derived_seed_publicly_recomputable": True,
            "seed_secrecy_claimed": False,
            "anti_shopping_order_verified": False,
            "entropy_custody_verified": False,
            "o_excl_sampling_receipt_created": False,
            "condition_output_authorized": False,
        },
    )
