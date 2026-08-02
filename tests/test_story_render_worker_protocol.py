from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs/design/voice-scene"
MODULE_PATH = ROOT / "scripts/story_render_worker_protocol.py"
CONTRACT_PATH = (
    VOICE_SCENE / "s620_story_render_one_shot_worker_protocol_contract.json"
)
REQUEST_SCHEMA_PATH = VOICE_SCENE / "story_render_worker_request.schema.json"
RESPONSE_SCHEMA_PATH = VOICE_SCENE / "story_render_worker_response.schema.json"

REQUEST_ID = "12" * 16
PROTOCOL = "agent_bridge.story-render-worker.v1"


def load_module():
    assert MODULE_PATH.exists(), "S622 protocol codec module is missing"
    spec = importlib.util.spec_from_file_location(
        "story_render_worker_protocol", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def request() -> dict:
    protocol_contract = contract()
    return {
        "protocol": PROTOCOL,
        "request_id": REQUEST_ID,
        "fixture": copy.deepcopy(protocol_contract["request"]["fixture"]),
        "authorization": {
            "authorization_id": "story-render-auth-" + "ab" * 16,
            "contract_sha256": protocol_contract["contract_sha256"],
            "preflight_sha256": protocol_contract["request"]["fixture"][
                "preflight_sha256"
            ],
            "output_directory": (
                protocol_contract["output_custody"]["root"] + "/" + REQUEST_ID
            ),
            "action": "render",
            "issued_at": "2026-08-02T12:00:00+00:00",
            "expires_at": "2026-08-02T12:05:00+00:00",
            "single_use_nonce": "cd" * 32,
            "issuer": "agent-bridge-owner-console",
            "subject": "story-bounded-render-executor",
            "key_id": "story-render-owner-v1",
            # Deliberately synthetic: S622 validates shape, never the MAC.
            "mac_sha256": "ef" * 32,
        },
    }


def success_response() -> dict:
    return {
        "protocol": PROTOCOL,
        "request_id": REQUEST_ID,
        "status": "success",
        "render_id": REQUEST_ID,
        "segment_count": 3,
        "assembly": {
            "sha256": "34" * 32,
            "sample_rate_hz": 24_000,
            "channels": 1,
            "frames": 72_000,
            "duration_seconds": 3.0,
        },
        "playback_authorized": False,
        "memory_authorized": False,
    }


def error_response() -> dict:
    return {
        "protocol": PROTOCOL,
        "request_id": REQUEST_ID,
        "status": "error",
        "code": "render_failed",
        "retryable": False,
    }


def encoded(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def assert_error(module, code: str, call) -> None:
    with pytest.raises(module.ProtocolError) as caught:
        call()
    assert caught.value.code == code
    assert str(caught.value) == code


def test_decode_request_accepts_only_the_fixed_bound_shape() -> None:
    module = load_module()
    supplied_contract = contract()
    value = request()
    before = copy.deepcopy(supplied_contract)

    decoded = module.decode_request(encoded(value), supplied_contract)

    assert decoded == value
    assert decoded is not value
    assert supplied_contract == before
    assert decoded["authorization"]["mac_sha256"] == "ef" * 32


@pytest.mark.parametrize(
    ("raw_factory", "code"),
    [
        (lambda value, spec: b" " * (spec["protocol"]["stdin_max_bytes"] + 1), "input_oversize"),
        (lambda value, _spec: b"\xff", "invalid_utf8"),
        (lambda value, _spec: b"[]", "invalid_json_root"),
        (
            lambda value, _spec: encoded(value)[:-1]
            + b',"protocol":"agent_bridge.story-render-worker.v1"}',
            "duplicate_json_key",
        ),
        (
            lambda value, _spec: encoded(value).replace(
                b'"chapter":2', b'"chapter":NaN'
            ),
            "nonfinite_number",
        ),
        (lambda value, _spec: encoded(value) + b"{}", "trailing_json_data"),
        (lambda value, _spec: encoded({**value, "text": "secret"}), "unknown_request_field"),
    ],
)
def test_decode_request_rejects_strict_json_failures(raw_factory, code: str) -> None:
    module = load_module()
    value = request()
    raw = raw_factory(value, contract())

    assert_error(module, code, lambda: module.decode_request(raw, contract()))


def test_decode_request_rejects_fixture_and_request_identity_drift() -> None:
    module = load_module()
    changed_fixture = request()
    changed_fixture["fixture"]["chapter"] = 3
    changed_identity = request()
    changed_identity["request_id"] = "ABC"

    assert_error(
        module,
        "fixture_binding_mismatch",
        lambda: module.decode_request(encoded(changed_fixture), contract()),
    )
    assert_error(
        module,
        "invalid_request_id",
        lambda: module.decode_request(encoded(changed_identity), contract()),
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda authorization, _spec: authorization.pop("issuer"),
        lambda authorization, _spec: authorization.update(extra="unsigned"),
        lambda authorization, _spec: authorization.update(contract_sha256="0" * 64),
        lambda authorization, _spec: authorization.update(preflight_sha256="0" * 64),
        lambda authorization, _spec: authorization.update(output_directory="/tmp/out"),
        lambda authorization, _spec: authorization.update(action="inspect"),
        lambda authorization, _spec: authorization.update(expires_at="2026-08-02T12:05:01+00:00"),
        lambda authorization, _spec: authorization.update(issued_at="not-a-time"),
        lambda authorization, _spec: authorization.update(mac_sha256="not-hex"),
    ],
)
def test_decode_request_rejects_authorization_shape_or_binding_drift(mutate) -> None:
    module = load_module()
    value = request()
    mutate(value["authorization"], contract())

    assert_error(
        module,
        "authorization_shape_invalid",
        lambda: module.decode_request(encoded(value), contract()),
    )


def test_protocol_errors_are_fixed_and_never_echo_input() -> None:
    module = load_module()
    marker = "TOP-SECRET-AUTHORIZATION-MARKER"
    value = request()
    value["authorization"]["issuer"] = marker
    value["authorization"]["unexpected"] = marker

    with pytest.raises(module.ProtocolError) as caught:
        module.decode_request(encoded(value), contract())

    assert caught.value.code == "authorization_shape_invalid"
    assert marker not in str(caught.value)
    assert marker not in repr(caught.value)


def test_validate_worker_response_accepts_closed_success_and_error_shapes() -> None:
    module = load_module()

    assert module.validate_worker_response(
        encoded(success_response()), contract(), expected_request_id=REQUEST_ID
    ) == success_response()
    assert module.validate_worker_response(
        encoded(error_response()), contract(), expected_request_id=REQUEST_ID
    ) == error_response()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(request_id="56" * 16),
        lambda value: value.update(render_id="56" * 16),
        lambda value: value.update(playback_authorized=True),
        lambda value: value.update(memory_authorized=True),
        lambda value: value.update(segment_count=0),
        lambda value: value["assembly"].update(frames=True),
        lambda value: value["assembly"].update(duration_seconds=float("inf")),
        lambda value: value["assembly"].update(extra="path"),
    ],
)
def test_validate_worker_response_rejects_malformed_success(mutation) -> None:
    module = load_module()
    value = success_response()
    mutation(value)

    if value["assembly"].get("duration_seconds") == float("inf"):
        raw = json.dumps(value, allow_nan=True).encode("utf-8")
    else:
        raw = encoded(value)
    assert_error(
        module,
        "malformed_worker_response",
        lambda: module.validate_worker_response(
            raw, contract(), expected_request_id=REQUEST_ID
        ),
    )


def test_validate_worker_response_rejects_forbidden_fields_anywhere() -> None:
    module = load_module()
    top_level = success_response()
    top_level["output_directory"] = "/private/path"
    nested = success_response()
    nested["assembly"]["traceback"] = "secret"

    for value in (top_level, nested):
        assert_error(
            module,
            "forbidden_response_field",
            lambda value=value: module.validate_worker_response(
                encoded(value), contract(), expected_request_id=REQUEST_ID
            ),
        )


def test_encode_error_response_is_deterministic_bounded_and_validated() -> None:
    module = load_module()

    encoded_error = module.encode_error_response(
        request_id=REQUEST_ID,
        code="render_failed",
        retryable=True,
        contract=contract(),
    )

    assert encoded_error == (
        b'{"code":"render_failed","protocol":"agent_bridge.story-render-worker.v1",'
        b'"request_id":"12121212121212121212121212121212","retryable":true,'
        b'"status":"error"}'
    )
    assert len(encoded_error) <= contract()["protocol"]["stdout_max_bytes"]
    assert module.validate_worker_response(
        encoded_error, contract(), expected_request_id=REQUEST_ID
    )["code"] == "render_failed"


def test_encode_error_response_uses_a_fixed_unknown_request_sentinel() -> None:
    module = load_module()

    raw = module.encode_error_response(
        request_id=None,
        code="invalid_request",
        retryable=False,
        contract=contract(),
    )

    assert json.loads(raw)["request_id"] == "0" * 32
    assert_error(
        module,
        "invalid_error_response",
        lambda: module.encode_error_response(
            request_id=REQUEST_ID,
            code="not-contract-defined",
            retryable=False,
            contract=contract(),
        ),
    )


def test_project_mcp_response_emits_only_the_contract_allowlist() -> None:
    module = load_module()
    response = success_response()

    projected = module.project_mcp_response(
        response, contract(), expected_request_id=REQUEST_ID
    )

    assert projected == {
        "status": "success",
        "render_id": REQUEST_ID,
        "segment_count": 3,
        "assembly": response["assembly"],
        "playback_authorized": False,
        "memory_authorized": False,
    }
    assert projected["assembly"] is not response["assembly"]
    assert module.project_mcp_response(
        error_response(), contract(), expected_request_id=REQUEST_ID
    ) == {"status": "error"}


def test_project_mcp_response_fails_closed_if_validation_is_bypassed() -> None:
    module = load_module()
    response = success_response()
    response["authorization_id"] = "must-not-leak"

    assert_error(
        module,
        "redaction_violation",
        lambda: module.project_mcp_response(
            response, contract(), expected_request_id=REQUEST_ID
        ),
    )


def test_codec_rejects_mutated_or_recomputed_contract_authority() -> None:
    module = load_module()
    changed = contract()
    changed["protocol"]["stdin_max_bytes"] = 1_000_000

    assert_error(
        module,
        "invalid_contract",
        lambda: module.decode_request(encoded(request()), changed),
    )

    changed["contract_sha256"] = module._canonical_sha256(
        {name: changed[name] for name in module.CONTRACT_DIGEST_FIELDS}
    )
    assert_error(
        module,
        "invalid_contract",
        lambda: module.decode_request(encoded(request()), changed),
    )


def test_request_and_response_schemas_are_closed_and_match_runtime_examples() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    request_schema = json.loads(REQUEST_SCHEMA_PATH.read_text(encoding="utf-8"))
    response_schema = json.loads(RESPONSE_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(request_schema)
    jsonschema.Draft202012Validator.check_schema(response_schema)

    assert list(
        jsonschema.Draft202012Validator(request_schema).iter_errors(request())
    ) == []
    assert list(
        jsonschema.Draft202012Validator(response_schema).iter_errors(
            success_response()
        )
    ) == []
    assert list(
        jsonschema.Draft202012Validator(response_schema).iter_errors(error_response())
    ) == []

    unknown_request = request()
    unknown_request["text"] = "caller supplied"
    unknown_response = success_response()
    unknown_response["absolute_path"] = "/private/path"
    assert list(
        jsonschema.Draft202012Validator(request_schema).iter_errors(unknown_request)
    )
    assert list(
        jsonschema.Draft202012Validator(response_schema).iter_errors(unknown_response)
    )


def test_codec_source_is_standard_library_pure_and_has_no_authority_surface() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            imported_roots.add((node.module or "").split(".")[0])

    assert imported_roots <= {"copy", "datetime", "hashlib", "json", "re", "typing"}
    for forbidden in (
        "subprocess",
        "sqlite3",
        "onnxruntime",
        "torch",
        "sounddevice",
        "pathlib",
        "os.environ",
        "getenv(",
        "open(",
        "write_text(",
        "write_bytes(",
        "datetime.now",
        "time.time",
        "random",
        "socket",
        "requests",
        "urllib",
        "import hmac",
        "compare_digest",
    ):
        assert forbidden not in source
