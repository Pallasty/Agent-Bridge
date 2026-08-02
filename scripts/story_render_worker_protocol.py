#!/usr/bin/env python3
"""Pure S622 codec for the fixed-fixture Story render worker protocol."""

from __future__ import annotations

import copy
from datetime import datetime
import hashlib
import json
import re
from typing import Any


EXPECTED_CONTRACT_SHA256 = (
    "be4bfc12d9adeda14b8d20048b91baaaf903f155a3fca5bd3413b2b649f7334d"
)
CONTRACT_DIGEST_FIELDS = (
    "evidence",
    "activation",
    "protocol",
    "request",
    "host_admission",
    "supervisor",
    "environment",
    "output_custody",
    "response",
    "lifecycle",
    "failure_policy",
    "implementation_authorized",
    "execution_authorized",
    "deployment_authorized",
    "runtime_effects",
)
UNKNOWN_REQUEST_ID = "0" * 32
_LOWER_HEX_32 = re.compile(r"^[0-9a-f]{32}$")
_LOWER_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class ProtocolError(ValueError):
    """A fixed-code protocol rejection that never carries caller input."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _DuplicateKey(ValueError):
    pass


class _NonFiniteNumber(ValueError):
    pass


def _fail(code: str) -> None:
    raise ProtocolError(code)


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateKey
        value[key] = item
    return value


def _reject_nonfinite(_token: str) -> None:
    raise _NonFiniteNumber


def _decode_json_object(
    raw: bytes,
    *,
    maximum_bytes: int,
    oversize_code: str,
    utf8_code: str,
    root_code: str,
    duplicate_code: str,
    nonfinite_code: str,
    trailing_code: str,
) -> dict[str, Any]:
    if not isinstance(raw, bytes):
        _fail(root_code)
    if len(raw) > maximum_bytes:
        _fail(oversize_code)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        _fail(utf8_code)
    decoder = json.JSONDecoder(
        object_pairs_hook=_strict_object,
        parse_constant=_reject_nonfinite,
    )
    stripped = text.lstrip()
    try:
        value, end = decoder.raw_decode(stripped)
    except _DuplicateKey:
        _fail(duplicate_code)
    except _NonFiniteNumber:
        _fail(nonfinite_code)
    except (json.JSONDecodeError, RecursionError):
        _fail(root_code)
    if stripped[end:].strip():
        _fail(trailing_code)
    if not isinstance(value, dict):
        _fail(root_code)
    return value


def _validated_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(contract, dict):
        _fail("invalid_contract")
    try:
        bound = {name: contract[name] for name in CONTRACT_DIGEST_FIELDS}
        protocol = contract["protocol"]
        request = contract["request"]
        authorization = request["authorization"]
        response = contract["response"]
        effects = contract["runtime_effects"]
        digest = _canonical_sha256(bound)
        valid = (
            contract.get("schema")
            == "agent_bridge.story_render_one_shot_worker_protocol.v1"
            and contract.get("status")
            == "story_render_one_shot_worker_protocol_reviewable"
            and contract.get("contract_sha256") == EXPECTED_CONTRACT_SHA256
            and digest == EXPECTED_CONTRACT_SHA256
            and protocol.get("name") == "agent_bridge.story-render-worker.v1"
            and protocol.get("encoding") == "strict_utf8_json_object"
            and protocol.get("framing") == "one_document_then_eof"
            and protocol.get("cardinality") == "one_request_one_response"
            and protocol.get("stdin_max_bytes") == 65_536
            and protocol.get("stdout_max_bytes") == 65_536
            and protocol.get("duplicate_object_keys_allowed") is False
            and protocol.get("nonfinite_numbers_allowed") is False
            and protocol.get("trailing_data_allowed") is False
            and request.get("exact_fields")
            == ["protocol", "request_id", "fixture", "authorization"]
            and request.get("protocol") == protocol["name"]
            and authorization.get("shape")
            == "s608_closed_hmac_sha256_envelope"
            and authorization.get("contract_sha256_binding")
            == "s620_protocol_contract_sha256"
            and authorization.get("preflight_sha256_binding")
            == "fixed_s602_preflight_sha256"
            and authorization.get("maximum_ttl_seconds") == 300
            and contract["output_custody"].get("render_id_relation")
            == "render_id_equals_request_id"
            and contract["output_custody"].get("absolute_paths_in_mcp_response")
            is False
            and response.get("playback_authorized") is False
            and response.get("memory_authorized") is False
            and contract.get("implementation_authorized") is False
            and contract.get("execution_authorized") is False
            and contract.get("deployment_authorized") is False
            and isinstance(effects, dict)
            and not any(effects.values())
        )
    except (KeyError, TypeError, ValueError):
        _fail("invalid_contract")
    if not valid:
        _fail("invalid_contract")
    return contract


def _is_nonempty_text(value: Any, *, maximum: int = 256) -> bool:
    return isinstance(value, str) and 0 < len(value) <= maximum


def _is_lower_hex(value: Any, pattern: re.Pattern[str]) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _aware_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _validate_authorization(
    authorization: Any,
    *,
    request_id: str,
    contract: dict[str, Any],
) -> None:
    authority_contract = contract["request"]["authorization"]
    expected_fields = set(authority_contract["exact_fields"])
    if not isinstance(authorization, dict) or set(authorization) != expected_fields:
        _fail("authorization_shape_invalid")
    if not all(_is_nonempty_text(authorization[name], maximum=4096)
               for name in expected_fields):
        _fail("authorization_shape_invalid")
    if any(
        not _is_nonempty_text(authorization[name])
        for name in ("authorization_id", "single_use_nonce", "issuer", "subject", "key_id")
    ):
        _fail("authorization_shape_invalid")
    fixture = contract["request"]["fixture"]
    expected_output = contract["output_custody"]["root"] + "/" + request_id
    if (
        not _is_lower_hex(authorization["contract_sha256"], _LOWER_HEX_64)
        or not _is_lower_hex(authorization["preflight_sha256"], _LOWER_HEX_64)
        or not _is_lower_hex(authorization["mac_sha256"], _LOWER_HEX_64)
        or authorization["contract_sha256"] != contract["contract_sha256"]
        or authorization["preflight_sha256"] != fixture["preflight_sha256"]
        or authorization["output_directory"] != expected_output
        or authorization["action"] != authority_contract["action"]
    ):
        _fail("authorization_shape_invalid")
    issued_at = _aware_timestamp(authorization["issued_at"])
    expires_at = _aware_timestamp(authorization["expires_at"])
    if issued_at is None or expires_at is None:
        _fail("authorization_shape_invalid")
    ttl_seconds = (expires_at - issued_at).total_seconds()
    if not 0 < ttl_seconds <= authority_contract["maximum_ttl_seconds"]:
        _fail("authorization_shape_invalid")


def decode_request(raw: bytes, contract: dict[str, Any]) -> dict[str, Any]:
    """Decode and shape-bind one request without verifying authority or doing I/O."""
    spec = _validated_contract(contract)
    value = _decode_json_object(
        raw,
        maximum_bytes=spec["protocol"]["stdin_max_bytes"],
        oversize_code="input_oversize",
        utf8_code="invalid_utf8",
        root_code="invalid_json_root",
        duplicate_code="duplicate_json_key",
        nonfinite_code="nonfinite_number",
        trailing_code="trailing_json_data",
    )
    expected_fields = set(spec["request"]["exact_fields"])
    actual_fields = set(value)
    if actual_fields - expected_fields:
        _fail("unknown_request_field")
    if actual_fields != expected_fields:
        _fail("invalid_request_shape")
    if value.get("protocol") != spec["request"]["protocol"]:
        _fail("invalid_request_shape")
    request_id = value.get("request_id")
    if not _is_lower_hex(request_id, _LOWER_HEX_32):
        _fail("invalid_request_id")
    if value.get("fixture") != spec["request"]["fixture"]:
        _fail("fixture_binding_mismatch")
    _validate_authorization(
        value.get("authorization"), request_id=request_id, contract=spec
    )
    return copy.deepcopy(value)


def _contains_forbidden_key(value: Any, forbidden: set[str]) -> bool:
    if isinstance(value, dict):
        return any(
            key in forbidden or _contains_forbidden_key(item, forbidden)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_key(item, forbidden) for item in value)
    return False


def _positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _positive_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value > 0
        and value == value
        and value not in (float("inf"), float("-inf"))
    )


def _validate_worker_response_value(
    value: Any,
    contract: dict[str, Any],
    *,
    expected_request_id: str,
) -> dict[str, Any]:
    response_contract = contract["response"]
    if not isinstance(value, dict):
        _fail("malformed_worker_response")
    forbidden = set(response_contract["forbidden_fields"])
    if _contains_forbidden_key(value, forbidden):
        _fail("forbidden_response_field")
    if (
        not _is_lower_hex(expected_request_id, _LOWER_HEX_32)
        or value.get("protocol") != contract["protocol"]["name"]
        or value.get("request_id") != expected_request_id
    ):
        _fail("malformed_worker_response")
    status = value.get("status")
    if status == "success":
        if set(value) != set(response_contract["success_exact_fields"]):
            _fail("malformed_worker_response")
        assembly = value.get("assembly")
        if (
            value.get("render_id") != expected_request_id
            or not _positive_integer(value.get("segment_count"))
            or value.get("playback_authorized") is not False
            or value.get("memory_authorized") is not False
            or not isinstance(assembly, dict)
            or set(assembly) != set(response_contract["assembly_exact_fields"])
            or not _is_lower_hex(assembly.get("sha256"), _LOWER_HEX_64)
            or not _positive_integer(assembly.get("sample_rate_hz"))
            or not _positive_integer(assembly.get("channels"))
            or not _positive_integer(assembly.get("frames"))
            or not _positive_finite_number(assembly.get("duration_seconds"))
        ):
            _fail("malformed_worker_response")
    elif status == "error":
        if (
            set(value) != set(response_contract["error_exact_fields"])
            or value.get("code") not in response_contract["error_codes"]
            or not isinstance(value.get("retryable"), bool)
        ):
            _fail("malformed_worker_response")
    else:
        _fail("malformed_worker_response")
    return copy.deepcopy(value)


def validate_worker_response(
    raw: bytes,
    contract: dict[str, Any],
    *,
    expected_request_id: str,
) -> dict[str, Any]:
    """Decode and validate one bounded Worker response."""
    spec = _validated_contract(contract)
    value = _decode_json_object(
        raw,
        maximum_bytes=spec["protocol"]["stdout_max_bytes"],
        oversize_code="malformed_worker_response",
        utf8_code="malformed_worker_response",
        root_code="malformed_worker_response",
        duplicate_code="malformed_worker_response",
        nonfinite_code="malformed_worker_response",
        trailing_code="malformed_worker_response",
    )
    return _validate_worker_response_value(
        value, spec, expected_request_id=expected_request_id
    )


def encode_error_response(
    *,
    request_id: str | None,
    code: str,
    retryable: bool,
    contract: dict[str, Any],
) -> bytes:
    """Encode one deterministic, contract-defined Worker error response."""
    spec = _validated_contract(contract)
    bound_request_id = UNKNOWN_REQUEST_ID if request_id is None else request_id
    if (
        not _is_lower_hex(bound_request_id, _LOWER_HEX_32)
        or code not in spec["response"]["error_codes"]
        or not isinstance(retryable, bool)
    ):
        _fail("invalid_error_response")
    response = {
        "protocol": spec["protocol"]["name"],
        "request_id": bound_request_id,
        "status": "error",
        "code": code,
        "retryable": retryable,
    }
    _validate_worker_response_value(
        response, spec, expected_request_id=bound_request_id
    )
    encoded = json.dumps(
        response,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > spec["protocol"]["stdout_max_bytes"]:
        _fail("invalid_error_response")
    return encoded


def project_mcp_response(
    response: dict[str, Any],
    contract: dict[str, Any],
    *,
    expected_request_id: str,
) -> dict[str, Any]:
    """Return only the S620 MCP projection allowlist after revalidation."""
    spec = _validated_contract(contract)
    try:
        validated = _validate_worker_response_value(
            response, spec, expected_request_id=expected_request_id
        )
    except ProtocolError:
        _fail("redaction_violation")
    allowlist = spec["response"]["mcp_projection_allowlist"]
    projected = {
        name: copy.deepcopy(validated[name])
        for name in allowlist
        if name in validated
    }
    if (
        set(projected) - set(allowlist)
        or _contains_forbidden_key(
            projected, set(spec["response"]["forbidden_fields"])
        )
    ):
        _fail("redaction_violation")
    return projected
