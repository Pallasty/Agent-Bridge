#!/usr/bin/env python3
"""Pure bounded JSON frame parser for one isolated-lab evidence-envelope KAT.

The public API intentionally has two layers:

``decode_frame(frame, mode)``
    Applies the pre-observation mode gate and then performs only closed,
    bounded byte framing and JSON decoding.  It has no envelope, trust,
    signer, time, replay, custody, or authority semantics.

``review_frame(frame, mode)``
    Applies the two exact track-specific variants of the closed-world
    isolated-lab KAT envelope contract.  The
    ``PRODUCTION`` call mode is rejected before the function reads, sizes,
    hashes, decodes, or otherwise observes ``frame``.  Consequently no
    supported public frame-ingress API can act as a production content oracle,
    and there is no production accepted state.

The module uses only the Python standard library and performs no file,
environment, clock, process, network, provider, credential, random, entropy,
mutable-global-state, or persistence I/O.  A successful receipt describes
only a deterministic nonsecret synthetic KAT.  It does not authenticate,
accept, ingest, quarantine, retain, or validate real evidence and does not
implement signer/trust, authorization, semantic validation, trusted time,
freshness, replay CAS, custody, independent review, owner handoff, or any
downstream authority gate.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping, NoReturn


MAX_INPUT_FRAME_BYTES = 1_048_576
MAX_JSON_DEPTH = 32
MAX_OBJECT_MEMBERS = 256
MAX_ARRAY_ITEMS = 64
MAX_JSON_NODES = 4_096
MIN_SIGNED_INT64 = -(2**63)
MAX_SIGNED_INT64 = 2**63 - 1

SYNTHETIC_KAT_MODE = "SYNTHETIC_KAT"
PRODUCTION_MODE = "PRODUCTION"

ENVELOPE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.production_evidence_envelope_bounded_frame_parser_and_synthetic_"
    "mode_separation_isolated_lab_kat.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.production_evidence_envelope_bounded_frame_parser_and_synthetic_"
    "mode_separation_isolated_lab_v1.receipt.v0"
)
PACKET_KIND = "SYNTHETIC_PRODUCTION_EVIDENCE_ENVELOPE_KAT"
HASH_DOMAIN = "AB_TRACK_B_PRODUCTION_EVIDENCE_ENVELOPE_ISOLATED_LAB_KAT_V1"
RECEIPT_HASH_DOMAIN = (
    "AB_TRACK_B_PRODUCTION_EVIDENCE_ENVELOPE_ISOLATED_LAB_KAT_RECEIPT_V1"
)
CANONICALIZATION = "AGENT_BRIDGE_CANONICAL_JSON_V1_SORTED_KEYS_COMPACT_UTF8"
STATUS = (
    "PRODUCTION_SHAPED_EVIDENCE_ENVELOPE_ISOLATED_LAB_SYNTHETIC_KAT_"
    "FRAME_REVIEWED_NO_PRODUCTION_AUTHORITY"
)
COMPONENT_STATE = "PARSED_ISOLATED_LAB_KAT_COMPONENT_ONLY"

TRACK_IDS = (
    "MANAGED_SPANNER_CLOUD_KMS",
    "SELF_HOSTED_ETCD_OPENBAO",
)
PREREQUISITE_ID = "FRAME_AND_PARSE"
FIXTURE_CASE_ID = "VALID_MINIMAL_FRAME_V1"
FIXTURE_PAYLOAD = "NONSECRET_DETERMINISTIC_UTF8_JSON_FRAME_KAT_V1"

ENVELOPE_KEYS = (
    "canonicalization",
    "fixture_case_id",
    "fixture_payload",
    "hash_domain",
    "packet_kind",
    "prerequisite_id",
    "production_admissible",
    "schema",
    "schema_version",
    "synthetic_fixture",
    "track_id",
)

_BOMS = (
    b"\x00\x00\xfe\xff",
    b"\xff\xfe\x00\x00",
    b"\xef\xbb\xbf",
    b"\xfe\xff",
    b"\xff\xfe",
)
_COMPRESSION_MAGICS = (
    b"\x1f\x8b",          # gzip
    b"PK\x03\x04",        # zip
    b"PK\x05\x06",        # empty zip archive
    b"PK\x07\x08",        # spanned zip archive
    b"BZh",               # bzip2
    b"\xfd7zXZ\x00",      # xz
    b"7z\xbc\xaf\x27\x1c", # 7z
    b"\x28\xb5\x2f\xfd", # zstd
    b"\x04\x22\x4d\x18", # lz4 frame
    b"\xff\x06\x00\x00sNaPpY", # snappy framed stream
    b"\x78\x01",          # zlib, no/low compression
    b"\x78\x9c",          # zlib, default compression
    b"\x78\xda",          # zlib, best compression
)
_OUTER_WHITESPACE = b" \t\r\n"
_REMOTE_KEY_NAMES = frozenset(
    {
        "$id",
        "$ref",
        "endpoint",
        "href",
        "provider_endpoint",
        "remote_ref",
        "remote_reference",
        "uri",
        "url",
    }
)
_COMPRESSION_KEY_NAMES = frozenset(
    {
        "codec",
        "compressed",
        "compression",
        "compression_algorithm",
        "compression_codec",
        "content_encoding",
    }
)
_COMPRESSION_STRING_VALUES = frozenset(
    {
        "application/gzip",
        "application/x-bzip2",
        "application/x-xz",
        "application/zip",
        "br",
        "bzip2",
        "deflate",
        "gzip",
        "lz4",
        "snappy",
        "xz",
        "7z",
        "zip",
        "zlib",
        "zstd",
    }
)
_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


class FrameReviewError(ValueError):
    """Fail-closed frame/review error with a stable machine reason code."""

    def __init__(
        self,
        code: str,
        detail: str,
        *,
        detail_code: str | None = None,
    ) -> None:
        self.code = code
        self.detail = detail
        self.detail_code = detail_code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise FrameReviewError(code, detail)


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        _fail(code, detail)


def _exact_keys(value: Mapping[str, Any], expected: Iterable[str]) -> None:
    _require(type(value) is dict, "E_ENVELOPE_ROOT", "object required")
    _require(
        set(value) == set(expected),
        "E_ENVELOPE_KEYS",
        "closed-world envelope key set drift",
    )


def _reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _fail("E_JSON_DUPLICATE_KEY", f"duplicate object key {key!r}")
        value[key] = item
    return value


def _parse_constant(token: str) -> NoReturn:
    _fail("E_JSON_NONFINITE", f"non-finite numeric token {token!r}")


def _parse_float(token: str) -> NoReturn:
    _fail("E_JSON_FLOAT_FORBIDDEN", f"floating-point token {token!r}")


def _parse_int(token: str) -> int:
    # The longest accepted token is -9223372036854775808 (20 bytes).  Reject
    # longer tokens before constructing an unbounded Python integer.
    if len(token) > 20:
        _fail("E_JSON_INTEGER_RANGE", "integer token exceeds signed int64 width")
    try:
        value = int(token, 10)
    except ValueError as error:
        _fail("E_JSON_INTEGER_RANGE", f"invalid integer token: {error}")
    if not MIN_SIGNED_INT64 <= value <= MAX_SIGNED_INT64:
        _fail("E_JSON_INTEGER_RANGE", "integer is outside signed int64 range")
    return value


def _reject_excessive_raw_depth(text: str) -> None:
    """Bound structural depth before invoking Python's recursive JSON scanner."""

    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "{[":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                _fail("E_JSON_DEPTH", f"JSON depth exceeds {MAX_JSON_DEPTH}")
        elif character in "}]":
            depth -= 1
            # Syntax diagnostics remain the decoder's job, but avoiding a
            # negative counter keeps this preflight deterministic.
            if depth < 0:
                depth = 0


def _has_invalid_scalar(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _normalized_shaped_key(key: str) -> str:
    """Normalize common camelCase and separator variants for shape guards."""

    return (
        _CAMEL_BOUNDARY_RE.sub("_", key)
        .replace("-", "_")
        .replace(".", "_")
        .casefold()
    )


def _remote_shaped_key(key: str) -> bool:
    lowered = _normalized_shaped_key(key)
    return (
        lowered in _REMOTE_KEY_NAMES
        or lowered.endswith("_endpoint")
        or lowered.endswith("_href")
        or lowered.endswith("_remote_ref")
        or lowered.endswith("_remote_reference")
        or lowered.endswith("_uri")
        or lowered.endswith("_url")
    )


def _compression_shaped_key(key: str) -> bool:
    lowered = _normalized_shaped_key(key)
    return lowered in _COMPRESSION_KEY_NAMES or lowered.endswith("_compression")


def _remote_shaped_value(value: str) -> bool:
    stripped = value.strip()
    return (
        _URI_SCHEME_RE.match(stripped) is not None
        or stripped.startswith("//")
        or stripped.startswith("\\\\")
    )


def _compression_shaped_value(value: str) -> bool:
    return value.strip().casefold() in _COMPRESSION_STRING_VALUES


def _inspect_shape(value: Any, depth: int = 1) -> dict[str, int]:
    """Validate bounded JSON types and return deterministic aggregate counts."""

    _require(depth <= MAX_JSON_DEPTH, "E_JSON_DEPTH", "post-decode depth drift")
    stats = {
        "array_count": 0,
        "array_item_count": 0,
        "json_depth": depth,
        "node_count": 1,
        "object_count": 0,
        "object_member_count": 0,
    }

    if value is None or type(value) is bool:
        return stats
    if type(value) is int:
        _require(
            MIN_SIGNED_INT64 <= value <= MAX_SIGNED_INT64,
            "E_JSON_INTEGER_RANGE",
            "decoded integer outside signed int64 range",
        )
        return stats
    if type(value) is str:
        _require(
            not _has_invalid_scalar(value),
            "E_JSON_UNICODE_SCALAR",
            "surrogate code point is forbidden",
        )
        _require(
            not _remote_shaped_value(value),
            "E_REMOTE_REFERENCE_FORBIDDEN",
            "URI or remote-reference value is forbidden",
        )
        _require(
            not _compression_shaped_value(value),
            "E_COMPRESSION_FORBIDDEN",
            "compression marker value is forbidden",
        )
        return stats
    if type(value) is float:
        _fail("E_JSON_FLOAT_FORBIDDEN", "decoded floating-point value")

    if type(value) is list:
        _require(
            len(value) <= MAX_ARRAY_ITEMS,
            "E_JSON_ARRAY_ITEMS",
            f"array has more than {MAX_ARRAY_ITEMS} items",
        )
        stats["array_count"] = 1
        stats["array_item_count"] = len(value)
        for item in value:
            child_depth = depth + 1 if type(item) in (dict, list) else depth
            child = _inspect_shape(item, child_depth)
            for field in stats:
                if field == "json_depth":
                    stats[field] = max(stats[field], child[field])
                else:
                    stats[field] += child[field]
            _require(
                stats["node_count"] <= MAX_JSON_NODES,
                "E_JSON_NODE_COUNT",
                f"JSON node count exceeds {MAX_JSON_NODES}",
            )
        return stats

    _require(type(value) is dict, "E_JSON_TYPE", "unsupported decoded JSON type")
    _require(
        len(value) <= MAX_OBJECT_MEMBERS,
        "E_JSON_OBJECT_MEMBERS",
        f"object has more than {MAX_OBJECT_MEMBERS} members",
    )
    stats["object_count"] = 1
    stats["object_member_count"] = len(value)
    for key, item in value.items():
        _require(type(key) is str, "E_JSON_KEY_TYPE", "object key is not text")
        _require(
            not _has_invalid_scalar(key),
            "E_JSON_UNICODE_SCALAR",
            "surrogate code point in object key is forbidden",
        )
        _require(
            not _remote_shaped_key(key),
            "E_REMOTE_REFERENCE_FORBIDDEN",
            f"remote-reference field {key!r} is forbidden",
        )
        _require(
            not _compression_shaped_key(key),
            "E_COMPRESSION_FORBIDDEN",
            f"compression field {key!r} is forbidden",
        )
        child_depth = depth + 1 if type(item) in (dict, list) else depth
        child = _inspect_shape(item, child_depth)
        for field in stats:
            if field == "json_depth":
                stats[field] = max(stats[field], child[field])
            else:
                stats[field] += child[field]
        _require(
            stats["node_count"] <= MAX_JSON_NODES,
            "E_JSON_NODE_COUNT",
            f"JSON node count exceeds {MAX_JSON_NODES}",
        )
    return stats


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        _fail("E_CANONICAL_JSON", str(error))


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _domain_sha256(domain: str, raw: bytes) -> str:
    try:
        prefix = domain.encode("ascii")
    except UnicodeEncodeError as error:
        _fail("E_HASH_DOMAIN", str(error))
    return _sha256(prefix + b"\x00" + raw)


def _reject_observation_mode(mode: str) -> None:
    """Reject production and unknown modes before any caller observes a frame."""

    if type(mode) is str and mode == PRODUCTION_MODE:
        _fail(
            "E_PRODUCTION_MODE_NOT_AUTHORIZED",
            "production frame observation is outside isolated-lab authority",
        )
    if type(mode) is not str or mode != SYNTHETIC_KAT_MODE:
        _fail("E_MODE_UNKNOWN", "only SYNTHETIC_KAT is locally reviewable")


def _decode_frame(frame: bytes) -> dict[str, Any]:
    """Decode one bounded exact UTF-8 JSON object after the mode gate."""

    _require(type(frame) is bytes, "E_FRAME_TYPE", "frame must be exact bytes")
    _require(len(frame) > 0, "E_FRAME_EMPTY", "frame must not be empty")
    _require(
        len(frame) <= MAX_INPUT_FRAME_BYTES,
        "E_FRAME_TOO_LARGE",
        f"frame exceeds {MAX_INPUT_FRAME_BYTES} bytes",
    )
    _require(
        not any(frame.startswith(magic) for magic in _BOMS),
        "E_BOM_FORBIDDEN",
        "Unicode BOM or alternate encoded frame is forbidden",
    )
    _require(
        not any(frame.startswith(magic) for magic in _COMPRESSION_MAGICS),
        "E_COMPRESSION_FORBIDDEN",
        "compressed frame magic is forbidden",
    )
    _require(
        frame[:1] not in _OUTER_WHITESPACE and frame[-1:] not in _OUTER_WHITESPACE,
        "E_FRAME_OUTER_WHITESPACE",
        "leading or trailing whitespace is forbidden",
    )

    try:
        text = frame.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        _fail("E_UTF8_INVALID", str(error))
    _reject_excessive_raw_depth(text)

    decoder = json.JSONDecoder(
        object_pairs_hook=_reject_pairs,
        parse_constant=_parse_constant,
        parse_float=_parse_float,
        parse_int=_parse_int,
        strict=True,
    )
    try:
        value, end = decoder.raw_decode(text)
    except FrameReviewError:
        raise
    except (json.JSONDecodeError, RecursionError) as error:
        _fail("E_JSON_SYNTAX", str(error))
    _require(
        end == len(text),
        "E_JSON_TRAILING_DATA",
        "trailing bytes or a second JSON value are forbidden",
    )
    _require(type(value) is dict, "E_JSON_ROOT_NOT_OBJECT", "root must be object")
    _inspect_shape(value)
    return value


def decode_frame(frame: bytes, mode: str) -> dict[str, Any]:
    """Mode-gate and decode one bounded exact UTF-8 JSON object.

    Production and unknown modes fail before ``frame`` is type-checked, sized,
    hashed, copied, compared, indexed, decoded, or parsed.
    """

    _reject_observation_mode(mode)
    return _decode_frame(frame)


def _require_kat_track(track_id: str) -> None:
    _require(
        type(track_id) is str and track_id in TRACK_IDS,
        "E_KAT_TRACK",
        "track_id must be one of the two frozen Track B tracks",
    )


def known_answer_envelope(
    track_id: str = TRACK_IDS[0],
) -> dict[str, Any]:
    """Return one exact track-specific nonsecret isolated-lab KAT envelope."""

    _require_kat_track(track_id)
    return {
        "canonicalization": CANONICALIZATION,
        "fixture_case_id": FIXTURE_CASE_ID,
        "fixture_payload": FIXTURE_PAYLOAD,
        "hash_domain": HASH_DOMAIN,
        "packet_kind": PACKET_KIND,
        "prerequisite_id": PREREQUISITE_ID,
        "production_admissible": False,
        "schema": ENVELOPE_SCHEMA,
        "schema_version": 1,
        "synthetic_fixture": True,
        "track_id": track_id,
    }


def known_answer_frame(track_id: str = TRACK_IDS[0]) -> bytes:
    """Return canonical compact bytes for one of the two track-specific KATs."""

    return _canonical_bytes(known_answer_envelope(track_id))


def _validate_envelope(envelope: Mapping[str, Any]) -> None:
    _exact_keys(envelope, ENVELOPE_KEYS)
    _require(
        type(envelope["track_id"]) is str and envelope["track_id"] in TRACK_IDS,
        "E_ENVELOPE_TRACK",
        "track_id is not one of the two frozen Track B tracks",
    )
    expected = known_answer_envelope(envelope["track_id"])
    checks = (
        ("schema", "E_ENVELOPE_SCHEMA"),
        ("schema_version", "E_ENVELOPE_SCHEMA_VERSION"),
        ("packet_kind", "E_ENVELOPE_PACKET_KIND"),
        ("hash_domain", "E_ENVELOPE_HASH_DOMAIN"),
        ("canonicalization", "E_ENVELOPE_CANONICALIZATION"),
        ("synthetic_fixture", "E_ENVELOPE_SYNTHETIC_FLAG"),
        ("production_admissible", "E_ENVELOPE_PRODUCTION_FLAG"),
        ("track_id", "E_ENVELOPE_TRACK"),
        ("prerequisite_id", "E_ENVELOPE_PREREQUISITE"),
        ("fixture_case_id", "E_ENVELOPE_FIXTURE_CASE"),
        ("fixture_payload", "E_ENVELOPE_FIXTURE_PAYLOAD"),
    )
    for field, code in checks:
        _require(
            type(envelope[field]) is type(expected[field])
            and envelope[field] == expected[field],
            code,
            f"{field} is not the frozen isolated-lab KAT value",
        )


def review_frame(frame: bytes, mode: str) -> dict[str, Any]:
    """Review the synthetic KAT or reject production before observing frame.

    ``PRODUCTION`` and unknown call modes have no content-dependent branch.
    In particular, the production path does not type-check, size, hash, copy,
    compare, index, decode, or parse ``frame``.
    """

    _reject_observation_mode(mode)

    try:
        envelope = _decode_frame(frame)
        canonical = _canonical_bytes(envelope)
        _require(
            canonical == frame,
            "E_FRAME_NONCANONICAL",
            "frame is not exact sorted-key compact UTF-8 canonical JSON",
        )
    except FrameReviewError as error:
        raise FrameReviewError(
            "E_PRODUCTION_FRAME_REJECTED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error
    try:
        _validate_envelope(envelope)
    except FrameReviewError as error:
        raise FrameReviewError(
            "E_SYNTHETIC_PRODUCTION_DOMAIN_REJECTED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error
    stats = _inspect_shape(envelope)
    receipt: dict[str, Any] = {
        "array_count": stats["array_count"],
        "array_item_count": stats["array_item_count"],
        "canonical_bytes_match_raw": canonical == frame,
        "canonical_frame_sha256": _sha256(canonical),
        "canonicalization": CANONICALIZATION,
        "component_state": COMPONENT_STATE,
        "content_sha256": "0" * 64,
        "custody_committed": False,
        "domain_separated_frame_sha256": _domain_sha256(HASH_DOMAIN, canonical),
        "downstream_gates_authorized": 0,
        "envelope_schema": ENVELOPE_SCHEMA,
        "evidence_acceptance_authorized": False,
        "execution_mode": SYNTHETIC_KAT_MODE,
        "frame_bytes": len(frame),
        "hash_domain": HASH_DOMAIN,
        "isolated_lab_candidate_surface_component_implemented": 2,
        "isolated_lab_candidate_surface_component_total": 2,
        "json_depth": stats["json_depth"],
        "node_count": stats["node_count"],
        "object_count": stats["object_count"],
        "object_member_count": stats["object_member_count"],
        "packet_kind": PACKET_KIND,
        "production_admissible": False,
        "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_ingestion_controls_runtime_exercised": 0,
        "production_validated_evidence_items": 0,
        "provider_authority": False,
        "raw_frame_sha256": _sha256(frame),
        "real_evidence_items_present": 0,
        "runtime_authority": False,
        "schema": RECEIPT_SCHEMA,
        "side_effects_unlocked": "NONE",
        "status": STATUS,
        "synthetic_fixture": True,
        "track_id": envelope["track_id"],
    }
    receipt_without_hash = dict(receipt)
    del receipt_without_hash["content_sha256"]
    receipt["content_sha256"] = _domain_sha256(
        RECEIPT_HASH_DOMAIN,
        _canonical_bytes(receipt_without_hash),
    )
    return receipt


def review_known_answer(track_id: str = TRACK_IDS[0]) -> dict[str, Any]:
    """Return the deterministic receipt for the one committed-shape KAT."""

    return review_frame(known_answer_frame(track_id), SYNTHETIC_KAT_MODE)


__all__ = [
    "CANONICALIZATION",
    "COMPONENT_STATE",
    "ENVELOPE_KEYS",
    "ENVELOPE_SCHEMA",
    "FIXTURE_CASE_ID",
    "FIXTURE_PAYLOAD",
    "FrameReviewError",
    "HASH_DOMAIN",
    "MAX_ARRAY_ITEMS",
    "MAX_INPUT_FRAME_BYTES",
    "MAX_JSON_DEPTH",
    "MAX_JSON_NODES",
    "MAX_OBJECT_MEMBERS",
    "MAX_SIGNED_INT64",
    "MIN_SIGNED_INT64",
    "PACKET_KIND",
    "PREREQUISITE_ID",
    "PRODUCTION_MODE",
    "RECEIPT_HASH_DOMAIN",
    "RECEIPT_SCHEMA",
    "STATUS",
    "SYNTHETIC_KAT_MODE",
    "TRACK_IDS",
    "decode_frame",
    "known_answer_envelope",
    "known_answer_frame",
    "review_frame",
    "review_known_answer",
]
