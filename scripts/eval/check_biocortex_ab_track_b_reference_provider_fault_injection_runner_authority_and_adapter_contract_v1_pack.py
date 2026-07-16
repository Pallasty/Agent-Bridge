#!/usr/bin/env python3
"""Validate the Track B runner-v1 authority and adapter-contract packet.

The checker deliberately implements its own JSON decoder, schema evaluator, and
contract oracle.  It never delegates validation to the packet source module.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Iterable


BASELINE_COMMIT = "b15a48d17fb30b0990bf26210978f2a4f78f54cc"
PREDECESSOR_SOURCE_COMMIT = "27fd73aa36ac897fb817398eca3a191181d8fb5d"
STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_AUTHORITY_AND_ADAPTER_"
    "CONTRACT_PREREGISTERED_NO_PROVIDER_NO_CREDENTIAL_NO_PERMIT"
)
DECISION = "RUNNER_AUTHORITY_AND_ADAPTER_CONTRACT_PASS_EXECUTION_REMAINS_BLOCKED"
CONTRACT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_adapter_contract.v1"
)
AUTHORITY_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_authority_bundle.v1"
)
STOP_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_stop_receipt.v1"
)
OBSERVATION_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_contract_source_observation.v0"
)
VALIDATION_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_contract_validation_receipt.v1"
)
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "OFFLINE_AUTHORITY_VERIFIER_AND_ADAPTER_DOUBLE_IMPLEMENTATION"
)
MANAGED_TRACK = "MANAGED_SPANNER_CLOUD_KMS"
SELF_HOSTED_TRACK = "SELF_HOSTED_ETCD_OPENBAO"
EXPECTED_CONTRACT_SHA256 = "d602d9f14f662145bd12f33304b2800bb9601ff4fd76634eb56c41b86aa17201"
EXPECTED_AUTHORITY_SCHEMA_SHA256 = "faea2234635441b0bc043b5d605a449decc61cc854e708f705f7bb09d58a7b90"
EXPECTED_STOP_SCHEMA_SHA256 = "7657cd25a9abf4037ce5eb4c403db36aebf4b43deb232886e62ff4afe9d45c36"
EXPECTED_SYNTHETIC_SHA256 = "75259e4d211d40d1b00caccd4b13ca593363884b507a59cd2b57b55c462f6300"
EXPECTED_SOURCE_SHA256 = "38b0e31504b72f961baec7e037a9340a334d3655aff2ce4d90fd01db4afb45a3"
OFFLINE_SUITE_ID = "f09b6eadaf59a4fe793bdbdd401fceccb7cb2a05a4f16357e7c1db5b1eba5731"

AUTHORITY_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-authority-receipt-schema-v1.json"
)
ADAPTER_CONTRACT_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-adapter-contract-v1.json"
)
STOP_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-stop-receipt-schema-v1.json"
)
SOURCE_PATH = Path(
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_authority_and_adapter_contract_v1.py"
)
CHECKER_PATH = Path(
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_authority_and_adapter_contract_v1_pack.py"
)
SYNTHETIC_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_authority_and_adapter_contract_v1_pack_synthetic_v0.json"
)
EXPECTED_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_authority_and_adapter_contract_v1_pack.expected.v0.tsv"
)
MANIFEST_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_authority_and_adapter_contract_v1_pack_v0.json"
)
REPORT_PATH = Path(
    "docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-"
    "injection-runner-authority-and-adapter-contract-v1-pack.md"
)
GATE_PATH = Path(
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-"
    "authority-and-adapter-contract-v1-pack.sh"
)
MANIFEST_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_contract_v1_pack_manifest.v0"
)
PACKET_PATHS = (
    ADAPTER_CONTRACT_PATH,
    AUTHORITY_SCHEMA_PATH,
    STOP_SCHEMA_PATH,
    SOURCE_PATH,
    CHECKER_PATH,
    SYNTHETIC_PATH,
    EXPECTED_PATH,
    MANIFEST_PATH,
    REPORT_PATH,
    GATE_PATH,
)

PREDECESSOR_PATHS = (
    Path("docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-schedule-entry-schema-v1.json"),
    Path("docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-run-row-schema-v1.json"),
    Path("docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-harness-suite-receipt-schema-v1.json"),
    Path("scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_harness_v1.py"),
    Path("scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack.py"),
    Path("scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack_synthetic_v0.json"),
    Path("scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack.expected.v0.tsv"),
    Path("scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack_v0.json"),
    Path("docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-injection-offline-harness-v1-pack.md"),
    Path("scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-offline-harness-v1-pack.sh"),
)
EXPECTED_PREDECESSOR_SHA256 = {
    str(PREDECESSOR_PATHS[0]): "135238e4f20ac6a5712606dc2b94aefaa9d6b54ec9dece234ac8f43381caa35b",
    str(PREDECESSOR_PATHS[1]): "a60b16cab0c1a3ac8314f4f4df19fae2cff59aa1a10e67fe446305dd70cb0ee1",
    str(PREDECESSOR_PATHS[2]): "711c85ce5d9c5eb13d5c39b65f684bb1d00cc9722ae03852b93a8352abbf2671",
    str(PREDECESSOR_PATHS[3]): "ed55297995d1f49d2b4f5b9c6116c4f5fd69ae5e2be0ea2658aae6b2ed7e0976",
    str(PREDECESSOR_PATHS[4]): "e05841c731dafcf9118e61937fa7f68a3810debb904124c590d07af1ced1f348",
    str(PREDECESSOR_PATHS[5]): "fd993935d9847f2a75b665cc77d078946cf2c0bd2d24adbd43c2a50d1dbd6a85",
    str(PREDECESSOR_PATHS[6]): "9c4a2f7ff0de15e5e37fd2d8b0292e8870eaa505102af04fa16c78c1eec50541",
    str(PREDECESSOR_PATHS[7]): "2e06aec1395957cd70ee86ab4af0452ca6c5da6a51112b4c21216bfd43e3a3ed",
    str(PREDECESSOR_PATHS[8]): "abedab430bb3d1b28bf508735f164569ae5878285324b35f28df13be3d5b6bf1",
    str(PREDECESSOR_PATHS[9]): "a8fc449406c599868322454d0f3bcc67ea21923441b04556db44a4dd3247f7cf",
}
EXPECTED_LINEAGE = {
    "baseline_commit": BASELINE_COMMIT,
    "offline_configuration_sha256": "fd993935d9847f2a75b665cc77d078946cf2c0bd2d24adbd43c2a50d1dbd6a85",
    "offline_harness_manifest_sha256": "2e06aec1395957cd70ee86ab4af0452ca6c5da6a51112b4c21216bfd43e3a3ed",
    "offline_rows_sha256": "e4458abb43b7de6d8fb40809e679393198b29c2303ba9824bae414455d6b305e",
    "offline_schedule_sha256": "37e00bb606b09760d0280e240afbbc2585412c7080a5bf909a130edf305d70b3",
    "predecessor_source_commit": PREDECESSOR_SOURCE_COMMIT,
    "preregistration_contract_sha256": "632dbf1d8202d94d6aef70d8b20c04050e647679da973d81afbe13d68344ad22",
}


class PackError(RuntimeError):
    """Stable failure with a mutation-testable error code."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def fail(code: str, message: str) -> None:
    raise PackError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


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
        fail("E_CANONICAL", f"cannot canonicalize JSON: {exc}")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def _reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "E_DUPLICATE_JSON_KEY", f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def decode_json(raw: bytes, label: str) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda token: fail(
                "E_NONFINITE_JSON", f"{label} contains {token}"
            ),
            object_pairs_hook=_reject_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("E_LOAD", f"cannot decode {label}: {exc}")


def load_canonical(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        fail("E_LOAD", f"cannot read {label}: {exc}")
    value = decode_json(raw, label)
    require(type(value) is dict, "E_ROOT_TYPE", f"{label} root must be an object")
    require(canonical_bytes(value) == raw, "E_NOT_CANONICAL", f"{label} is not canonical JSON")
    return value, raw


def _same_json_scalar(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def _json_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(
            _json_equal(left[key], right[key]) for key in left
        )
    if type(left) is list:
        return len(left) == len(right) and all(
            _json_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def _type_matches(instance: Any, expected: str) -> bool:
    return {
        "object": type(instance) is dict,
        "array": type(instance) is list,
        "string": type(instance) is str,
        "integer": type(instance) is int,
        "number": type(instance) in (int, float) and type(instance) is not bool,
        "boolean": type(instance) is bool,
        "null": instance is None,
    }.get(expected, False)


def _resolve_pointer(document: dict[str, Any], reference: str) -> dict[str, Any]:
    require(reference.startswith("#/"), "E_SCHEMA_REF", f"external ref forbidden: {reference}")
    value: Any = document
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        require(type(value) is dict and part in value, "E_SCHEMA_REF", f"unresolved ref: {reference}")
        value = value[part]
    require(type(value) is dict, "E_SCHEMA_REF", f"ref target is not a schema: {reference}")
    return value


def _probe_schema(instance: Any, schema: dict[str, Any], root: dict[str, Any]) -> bool:
    try:
        validate_json_schema(instance, schema, root_schema=root)
        return True
    except PackError:
        return False


def validate_json_schema(
    instance: Any,
    schema: dict[str, Any] | bool,
    *,
    root_schema: dict[str, Any] | None = None,
    path: str = "$",
) -> None:
    """Evaluate the closed Draft 2020-12 subset used by this packet."""

    if schema is True:
        return
    require(schema is not False, "E_SCHEMA_FALSE", f"{path} rejected by false schema")
    require(type(schema) is dict, "E_SCHEMA_DOCUMENT", f"schema at {path} is not an object")
    root = root_schema or schema

    if "$ref" in schema:
        validate_json_schema(
            instance,
            _resolve_pointer(root, schema["$ref"]),
            root_schema=root,
            path=path,
        )

    if "allOf" in schema:
        for subschema in schema["allOf"]:
            validate_json_schema(instance, subschema, root_schema=root, path=path)
    if "anyOf" in schema:
        matches = sum(_probe_schema(instance, item, root) for item in schema["anyOf"])
        require(matches >= 1, "E_SCHEMA_ANY_OF", f"{path} does not match any branch")
    if "oneOf" in schema:
        matches = sum(_probe_schema(instance, item, root) for item in schema["oneOf"])
        require(matches == 1, "E_SCHEMA_ONE_OF", f"{path} matches {matches} branches")
    if "not" in schema:
        require(
            not _probe_schema(instance, schema["not"], root),
            "E_SCHEMA_NOT",
            f"{path} matches forbidden branch",
        )
    if "if" in schema:
        branch = schema.get("then") if _probe_schema(instance, schema["if"], root) else schema.get("else")
        if branch is not None:
            validate_json_schema(instance, branch, root_schema=root, path=path)

    if "const" in schema:
        require(
            _json_equal(instance, schema["const"]),
            "E_SCHEMA_CONST",
            f"{path} const mismatch",
        )
    if "enum" in schema:
        require(
            any(_json_equal(instance, item) for item in schema["enum"]),
            "E_SCHEMA_ENUM",
            f"{path} enum mismatch",
        )

    expected_types = schema.get("type")
    if expected_types is not None:
        if type(expected_types) is str:
            expected_types = [expected_types]
        require(
            type(expected_types) is list
            and all(type(item) is str for item in expected_types),
            "E_SCHEMA_DOCUMENT",
            f"invalid type keyword at {path}",
        )
        require(
            any(_type_matches(instance, expected) for expected in expected_types),
            "E_SCHEMA_TYPE",
            f"{path} type mismatch",
        )

    if type(instance) is dict:
        properties = schema.get("properties", {})
        pattern_properties = schema.get("patternProperties", {})
        required = schema.get("required", [])
        require(
            all(type(key) is str for key in required),
            "E_SCHEMA_DOCUMENT",
            f"invalid required keyword at {path}",
        )
        for key in required:
            require(key in instance, "E_SCHEMA_REQUIRED", f"{path}.{key} is required")
        if "minProperties" in schema:
            require(len(instance) >= schema["minProperties"], "E_SCHEMA_MIN_PROPERTIES", f"{path} too small")
        if "maxProperties" in schema:
            require(len(instance) <= schema["maxProperties"], "E_SCHEMA_MAX_PROPERTIES", f"{path} too large")
        for key, value in instance.items():
            matched = False
            if key in properties:
                validate_json_schema(value, properties[key], root_schema=root, path=f"{path}.{key}")
                matched = True
            for pattern, subschema in pattern_properties.items():
                if re.search(pattern, key):
                    validate_json_schema(value, subschema, root_schema=root, path=f"{path}.{key}")
                    matched = True
            if not matched:
                extra = schema.get("additionalProperties", True)
                require(extra is not False, "E_SCHEMA_EXTRA", f"{path}.{key} is not allowed")
                if type(extra) is dict:
                    validate_json_schema(value, extra, root_schema=root, path=f"{path}.{key}")
        dependencies = schema.get("dependentRequired", {})
        for key, dependents in dependencies.items():
            if key in instance:
                for dependent in dependents:
                    require(dependent in instance, "E_SCHEMA_DEPENDENT", f"{path}.{dependent} required by {key}")

    if type(instance) is list:
        if "minItems" in schema:
            require(len(instance) >= schema["minItems"], "E_SCHEMA_MIN_ITEMS", f"{path} too short")
        if "maxItems" in schema:
            require(len(instance) <= schema["maxItems"], "E_SCHEMA_MAX_ITEMS", f"{path} too long")
        if schema.get("uniqueItems"):
            for index, item in enumerate(instance):
                require(
                    not any(_json_equal(item, prior) for prior in instance[:index]),
                    "E_SCHEMA_UNIQUE",
                    f"{path}[{index}] is duplicated",
                )
        prefix_items = schema.get("prefixItems", [])
        for index, subschema in enumerate(prefix_items[: len(instance)]):
            validate_json_schema(instance[index], subschema, root_schema=root, path=f"{path}[{index}]")
        items = schema.get("items")
        if items is not None:
            start = len(prefix_items)
            for index, item in enumerate(instance[start:], start=start):
                validate_json_schema(item, items, root_schema=root, path=f"{path}[{index}]")

    if type(instance) is str:
        if "minLength" in schema:
            require(len(instance) >= schema["minLength"], "E_SCHEMA_MIN_LENGTH", f"{path} too short")
        if "maxLength" in schema:
            require(len(instance) <= schema["maxLength"], "E_SCHEMA_MAX_LENGTH", f"{path} too long")
        if "pattern" in schema:
            require(re.search(schema["pattern"], instance) is not None, "E_SCHEMA_PATTERN", f"{path} pattern mismatch")

    if type(instance) in (int, float) and type(instance) is not bool:
        if "minimum" in schema:
            require(instance >= schema["minimum"], "E_SCHEMA_MINIMUM", f"{path} below minimum")
        if "maximum" in schema:
            require(instance <= schema["maximum"], "E_SCHEMA_MAXIMUM", f"{path} above maximum")
        if "exclusiveMinimum" in schema:
            require(instance > schema["exclusiveMinimum"], "E_SCHEMA_MINIMUM", f"{path} below exclusive minimum")
        if "exclusiveMaximum" in schema:
            require(instance < schema["exclusiveMaximum"], "E_SCHEMA_MAXIMUM", f"{path} above exclusive maximum")


_SCHEMA_META_KEYS = {
    "$schema",
    "$id",
    "$defs",
    "$comment",
    "title",
    "description",
    "default",
    "examples",
}
_SCHEMA_KEYWORDS = _SCHEMA_META_KEYS | {
    "$ref",
    "type",
    "const",
    "enum",
    "allOf",
    "anyOf",
    "oneOf",
    "not",
    "if",
    "then",
    "else",
    "properties",
    "patternProperties",
    "additionalProperties",
    "required",
    "minProperties",
    "maxProperties",
    "dependentRequired",
    "items",
    "prefixItems",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
}


def validate_schema_document(schema: dict[str, Any], expected_id: str, label: str) -> None:
    require(
        schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
        "E_SCHEMA_DRAFT",
        f"{label} must declare Draft 2020-12",
    )
    require(schema.get("$id") == expected_id, "E_SCHEMA_ID", f"{label} id mismatch")

    closed_property_names: set[str] = set()

    def collect_closed(node: Any) -> None:
        if type(node) is list:
            for item in node:
                collect_closed(item)
            return
        if type(node) is not dict:
            return
        if node.get("type") == "object" and type(node.get("properties")) is dict:
            closed_property_names.update(node["properties"])
        for value in node.values():
            collect_closed(value)

    collect_closed(schema)

    def walk(
        node: Any,
        path: str,
        is_schema: bool = True,
        narrowing_allowed: bool = False,
    ) -> None:
        if type(node) is list:
            for index, item in enumerate(node):
                walk(
                    item,
                    f"{path}[{index}]",
                    is_schema=is_schema,
                    narrowing_allowed=narrowing_allowed,
                )
            return
        if type(node) is not dict:
            return
        if is_schema:
            unknown = set(node) - _SCHEMA_KEYWORDS
            require(not unknown, "E_SCHEMA_KEYWORD", f"{path} unknown keywords: {sorted(unknown)}")
            # A pure narrowing branch after an allOf $ref may contain only
            # properties/required.  The referenced base is the independently
            # instance-bearing object and carries the closure fence.
            objectish = node.get("type") == "object"
            if objectish:
                require(
                    node.get("additionalProperties") is False,
                    "E_SCHEMA_OPEN_OBJECT",
                    f"{path} is not root-closed",
                )
            elif "properties" in node or "required" in node:
                require(
                    narrowing_allowed,
                    "E_SCHEMA_OBJECT_TYPE",
                    f"{path} dropped its object type/closure fence",
                )
                properties = node.get("properties", {})
                required = node.get("required", [])
                require(
                    type(properties) is dict and type(required) is list,
                    "E_SCHEMA_NARROWING",
                    f"{path} narrowing shape invalid",
                )
                require(
                    set(properties).issubset(closed_property_names)
                    and set(required).issubset(set(properties)),
                    "E_SCHEMA_NARROWING",
                    f"{path} does not narrow known closed properties",
                )
            for key, value in node.items():
                if key in {"properties", "patternProperties", "$defs"}:
                    require(type(value) is dict, "E_SCHEMA_DOCUMENT", f"{path}.{key} must be an object")
                    for child_key, child in value.items():
                        walk(
                            child,
                            f"{path}.{key}.{child_key}",
                            is_schema=True,
                            narrowing_allowed=(narrowing_allowed and key != "$defs"),
                        )
                elif key in {"allOf", "anyOf", "oneOf", "prefixItems"}:
                    walk(
                        value,
                        f"{path}.{key}",
                        is_schema=True,
                        narrowing_allowed=(key == "allOf" or narrowing_allowed),
                    )
                elif key in {"not", "if", "then", "else", "items", "additionalProperties"} and type(value) in (dict, bool):
                    walk(
                        value,
                        f"{path}.{key}",
                        is_schema=True,
                        narrowing_allowed=key in {"if", "then", "else"},
                    )
        else:
            for key, value in node.items():
                walk(value, f"{path}.{key}", is_schema=False)

    walk(schema, "$", is_schema=True, narrowing_allowed=False)


_ALLOWED_SOURCE_IMPORTS = {
    "__future__",
    "copy",
    "hashlib",
    "json",
    "re",
    "typing",
}
_FORBIDDEN_CALL_NAMES = {
    "open",
    "input",
    "exec",
    "eval",
    "compile",
    "breakpoint",
    "__import__",
    "getattr",
    "setattr",
    "globals",
    "locals",
    "vars",
}
_FORBIDDEN_ATTRIBUTE_CALLS = {
    "read_bytes",
    "read_text",
    "write_bytes",
    "write_text",
    "open",
    "unlink",
    "mkdir",
    "rmdir",
    "rename",
    "iterdir",
    "glob",
    "rglob",
    "getenv",
    "system",
    "popen",
    "run",
    "call",
    "check_call",
    "check_output",
    "urlopen",
    "request",
    "connect",
    "send",
    "recv",
}
_FORBIDDEN_SOURCE_TOKENS = (
    "os.environ",
    "os.getenv",
    "defaultcredentials",
    "application_default_credentials",
    "metadata.google.internal",
    "169.254.169.254",
)


def _validate_source_text(source: str, label: str) -> None:
    try:
        tree = ast.parse(source, filename=label)
    except SyntaxError as exc:
        fail("E_SOURCE_LOAD", f"cannot parse source: {exc}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] in _ALLOWED_SOURCE_IMPORTS, "E_SOURCE_IMPORT", f"forbidden import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            require(module.split(".")[0] in _ALLOWED_SOURCE_IMPORTS, "E_SOURCE_IMPORT", f"forbidden import {module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(node.func.id not in _FORBIDDEN_CALL_NAMES, "E_SOURCE_CALL", f"forbidden call {node.func.id}")
            elif isinstance(node.func, ast.Attribute):
                require(node.func.attr not in _FORBIDDEN_ATTRIBUTE_CALLS, "E_SOURCE_CALL", f"forbidden attribute call {node.func.attr}")
        elif isinstance(node, ast.Global):
            fail("E_SOURCE_GLOBAL", "source may not mutate global process state")

    folded = re.sub(r"[^a-z0-9._]+", "", source.lower())
    for token in _FORBIDDEN_SOURCE_TOKENS:
        require(token.replace("_", "") not in folded.replace("_", ""), "E_SOURCE_TOKEN", f"forbidden source capability token {token}")


def validate_source_ast(path: Path) -> str:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        fail("E_SOURCE_LOAD", f"cannot read source: {exc}")
    _validate_source_text(source, str(path))
    return source


def load_source_module(path: Path) -> tuple[Any, str]:
    source = validate_source_ast(path)
    spec = importlib.util.spec_from_file_location("_runner_contract_source", path)
    require(spec is not None and spec.loader is not None, "E_SOURCE_IMPORT", "cannot build source module spec")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - normalized pack failure
        fail("E_SOURCE_IMPORT", f"source import failed: {exc}")
    return module, source


def _expect_code(code: str, call: Callable[[], None], label: str) -> None:
    try:
        call()
    except PackError as exc:
        require(exc.code == code, "E_SELF_TEST_CODE", f"{label}: expected {code}, got {exc.code}")
    else:
        fail("E_SELF_TEST_MISSED", f"{label}: mutation was accepted")


def _expect_failure(call: Callable[[], None], label: str) -> None:
    try:
        call()
    except (PackError, Exception) as exc:
        # Candidate ContractError is intentionally not imported or trusted;
        # any ordinary exception from a directed candidate mutation is a
        # rejection, while BaseException classes remain unsuppressed.
        require(not isinstance(exc, (KeyboardInterrupt, SystemExit)), "E_SELF_TEST_EXCEPTION", f"{label}: unsafe exception")
        return
    fail("E_SELF_TEST_MISSED", f"{label}: mutation was accepted")


def run_loader_self_tests() -> int:
    count = 0
    _expect_code(
        "E_DUPLICATE_JSON_KEY",
        lambda: decode_json(b'{"a":1,"a":2}\n', "duplicate probe"),
        "duplicate JSON key",
    )
    count += 1
    _expect_code(
        "E_NONFINITE_JSON",
        lambda: decode_json(b'{"a":NaN}\n', "nonfinite probe"),
        "nonfinite JSON",
    )
    count += 1
    source_probes = (
        "import os\n",
        "open('credential.json')\n",
        "__import__('socket')\n",
        "getattr(object(), 'read_text')()\n",
        "from google.cloud import kms\n",
        "import subprocess\nsubprocess.run(['true'])\n",
    )
    for index, probe in enumerate(source_probes):
        _expect_failure(
            lambda probe=probe, index=index: _validate_source_text(probe, f"source purity probe {index}"),
            f"source purity probe {index}",
        )
        count += 1
    return count


def validate_predecessor_artifacts(root: Path) -> None:
    require(
        set(EXPECTED_PREDECESSOR_SHA256) == {str(path) for path in PREDECESSOR_PATHS},
        "E_PREDECESSOR_CATALOG",
        "predecessor hash catalog is incomplete",
    )
    for path in PREDECESSOR_PATHS:
        try:
            raw = (root / path).read_bytes()
        except OSError as exc:
            fail("E_PREDECESSOR_LOAD", f"cannot read predecessor {path}: {exc}")
        require(
            sha256_bytes(raw) == EXPECTED_PREDECESSOR_SHA256[str(path)],
            "E_PREDECESSOR_HASH",
            f"predecessor artifact drift: {path}",
        )


def exact_keys(value: Any, expected: Iterable[str], code: str, label: str) -> None:
    require(type(value) is dict, code, f"{label} must be an object")
    expected_set = set(expected)
    require(set(value) == expected_set, code, f"{label} fields drift")


def require_equal(actual: Any, expected: Any, code: str, label: str) -> None:
    require(_json_equal(actual, expected), code, f"{label} drift")


EXPECTED_TOP_LEVEL_KEYS = {
    "acceptance_policy",
    "adapter_interfaces",
    "authority_integrity",
    "authority_model",
    "baseline_commit",
    "boundary",
    "credential_isolation",
    "date",
    "decision",
    "evidence_contract",
    "execution_plan",
    "next_unit",
    "non_claims",
    "official_source_claims",
    "predecessor",
    "profile_contract",
    "purpose",
    "recovery_protocol",
    "retained_row_contract",
    "s12_branch_contract",
    "schema",
    "start_stop_logic",
    "status",
    "stop_control_plane",
    "version",
}
EXPECTED_AUTHORITY_ARTIFACTS = [
    "OWNER_SCOPE_RECEIPT",
    "CUSTODIAN_CREDENTIAL_RECEIPT",
    "RESOURCE_AUTHORITY_RECEIPT",
    "COST_AUTHORITY_RECEIPT",
    "EMERGENCY_STOP_AUTHORITY_RECEIPT",
]
EXPECTED_AUTHORITY_BINDING_FIELDS = [
    "TRACK_ID",
    "AUTHORIZATION_PHASE",
    "SUITE_ID",
    "SIMULATION_RUN_ID",
    "NAMESPACE_ID",
    "ASSIGNMENT_SHA256",
    "PREREGISTRATION_CONTRACT_SHA256",
    "OFFLINE_HARNESS_MANIFEST_SHA256",
    "PROVIDER_PROFILE_SHA256",
    "CONFIGURATION_SHA256",
    "SCHEDULE_SHA256",
    "RUNNER_BUILD_SHA256",
    "ADAPTER_BUILD_SHA256",
    "ADAPTER_SET_MANIFEST_SHA256",
    "STOP_CONTROL_PLANE_MANIFEST_SHA256",
    "CASE_AND_REPETITION_SCOPE",
    "RESOURCE_SCOPE_SHA256",
    "CREDENTIAL_SCOPE_SHA256",
    "COST_SCOPE_SHA256",
    "RETENTION_POLICY_SHA256",
    "CLEANUP_POLICY_SHA256",
    "FIELD_LEVEL_INTERSECTION_SHA256",
    "EFFECTIVE_ALLOWED_OPERATIONS",
    "CURRENTNESS_AND_REVOCATION_EPOCH",
]
EXPECTED_START_CONDITIONS = [
    "EXACT_PHASE_AND_TRACK_AUTHORITY",
    "ALL_FIVE_AUTHORITY_ARTIFACTS_AUTHENTIC_CURRENT_AND_UNREVOKED",
    "EXACT_SUITE_SIMULATION_RUN_NAMESPACE_ASSIGNMENT_PROFILE_CONFIGURATION_SCHEDULE_RUNNER_ADAPTER_ADAPTER_SET_AND_STOP_CONTROL_PLANE_BINDINGS",
    "RECOMPUTED_CASE_REPETITION_OPERATION_INTERSECTION_AND_EXACT_RESOURCE_CREDENTIAL_COST_RETENTION_CLEANUP_SCOPES_MATCH",
    "OPAQUE_CAPABILITY_STATE_UNUSED_DURABLE_CAS_UNCONSUMED_SINGLE_USE_AND_UNEXPOSED",
    "EVIDENCE_AND_RETENTION_PATH_READY",
    "NO_STOP_CONDITION_PRESENT",
]
EXPECTED_STOP_TRIGGERS = [
    "AUTHORITY_EXPIRED_REVOKED_OR_CURRENTNESS_FAILED",
    "PROFILE_CONFIGURATION_SCHEDULE_RUNNER_ADAPTER_ADAPTER_SET_ASSIGNMENT_OR_RESOURCE_DRIFT",
    "CREDENTIAL_LEASE_OR_COST_SCOPE_BREACH",
    "EXTRA_WIRE_ATTEMPT_OR_HIDDEN_RETRY",
    "FAULT_MISFIRE_MULTIPLE_TRIGGER_OR_CROSS_NAMESPACE_EFFECT",
    "EVIDENCE_WRITE_FAILURE_OR_SECRET_EXPOSURE",
    "WITNESS_UNAVAILABLE_STALE_FORKED_CONFLICTING_OR_NOT_INDEPENDENT",
    "UNKNOWN_PROVIDER_CALL_OR_UNCLOSED_AMBIGUITY",
    "OUTPUT_PERMIT_CONDITION_OUTPUT_OR_OTHER_BOUNDARY_BREACH",
    "OWNER_CUSTODIAN_OR_EMERGENCY_OPERATOR_STOP",
]
EXPECTED_STOP_ACTIONS = [
    "BLOCK_NEW_CALLS_AND_INVALIDATE_CAPABILITY",
    "RETAIN_CURRENT_ROW_AND_DURABLE_STATE",
    "DISARM_FAULT_CONTROLLER_AND_ISOLATE_EGRESS",
    "REQUEST_CREDENTIAL_REVOCATION",
    "PRESERVE_EVIDENCE_BEFORE_SCOPED_CLEANUP",
    "EMIT_STOP_RECEIPT_AND_ESCALATE_UNRESOLVED_AMBIGUITY",
]
EXPECTED_TRIGGER_REASON_ROLE_MAP = {
    "AUTHORITY_EXPIRED_REVOKED_OR_CURRENTNESS_FAILED": {
        "reasons": ["AUTHORITY_CURRENTNESS_FAILURE", "AUTHORITY_EXPIRED", "AUTHORITY_REVOKED"],
        "roles": ["SYSTEM_EXPIRY_OR_REVOCATION"],
    },
    "CREDENTIAL_LEASE_OR_COST_SCOPE_BREACH": {
        "reasons": ["COST_OR_RESOURCE_SCOPE_EXCEEDED", "CREDENTIAL_LEASE_OR_SCOPE_BREACH"],
        "roles": ["SYSTEM_BOUNDARY"],
    },
    "EVIDENCE_WRITE_FAILURE_OR_SECRET_EXPOSURE": {
        "reasons": ["EVIDENCE_PERSIST_FAILURE", "EVIDENCE_SINK_UNAVAILABLE", "SECRET_EXPOSURE"],
        "roles": ["SYSTEM_BOUNDARY"],
    },
    "EXTRA_WIRE_ATTEMPT_OR_HIDDEN_RETRY": {
        "reasons": ["EXTRA_OR_UNKNOWN_WIRE_ATTEMPT"],
        "roles": ["SYSTEM_BOUNDARY"],
    },
    "FAULT_MISFIRE_MULTIPLE_TRIGGER_OR_CROSS_NAMESPACE_EFFECT": {
        "reasons": ["CROSS_NAMESPACE_EFFECT", "FAULT_MISFIRE", "MULTIPLE_FAULT_TRIGGER"],
        "roles": ["SYSTEM_BOUNDARY"],
    },
    "OUTPUT_PERMIT_CONDITION_OUTPUT_OR_OTHER_BOUNDARY_BREACH": {
        "reasons": ["BOUNDARY_BREACH", "OUTPUT_OR_PERMIT_ATTEMPT"],
        "roles": ["SYSTEM_BOUNDARY"],
    },
    "OWNER_CUSTODIAN_OR_EMERGENCY_OPERATOR_STOP": {
        "reasons": ["OPERATOR_STOP"],
        "roles": ["CUSTODIAN", "EMERGENCY_OPERATOR", "OWNER"],
    },
    "PROFILE_CONFIGURATION_SCHEDULE_RUNNER_ADAPTER_ADAPTER_SET_ASSIGNMENT_OR_RESOURCE_DRIFT": {
        "reasons": ["BUILD_OR_PROFILE_DRIFT", "CONFIGURATION_OR_SCHEDULE_DRIFT", "RESOURCE_SCOPE_DRIFT"],
        "roles": ["SYSTEM_BOUNDARY"],
    },
    "UNKNOWN_PROVIDER_CALL_OR_UNCLOSED_AMBIGUITY": {
        "reasons": ["UNKNOWN_PROVIDER_CALL", "UNRESOLVED_AMBIGUITY"],
        "roles": ["SYSTEM_BOUNDARY"],
    },
    "WITNESS_UNAVAILABLE_STALE_FORKED_CONFLICTING_OR_NOT_INDEPENDENT": {
        "reasons": ["WITNESS_CURRENTNESS_FAILURE"],
        "roles": ["SYSTEM_BOUNDARY"],
    },
}
EXPECTED_MANAGED_ADAPTER_IDS = [
    "SPANNER_AUTHORITY_ADAPTER",
    "CLOUD_KMS_SIGNER_ADAPTER",
    "MANAGED_FAULT_PROXY_ADAPTER",
    "MANAGED_EVIDENCE_COLLECTOR_ADAPTER",
]
EXPECTED_SELF_HOSTED_ADAPTER_IDS = [
    "ETCD_AUTHORITY_ADAPTER",
    "OPENBAO_TRANSIT_ADAPTER",
    "EXTERNAL_RESTORE_WITNESS_ADAPTER",
    "LAB_FAULT_CONTROLLER_ADAPTER",
    "SELF_HOSTED_EVIDENCE_COLLECTOR_ADAPTER",
]
EXPECTED_CREDENTIAL_CLASSES = [
    "MANAGED_SPANNER_DATA_PLANE",
    "MANAGED_KMS_SIGN",
    "MANAGED_FAULT_PROXY_CONTROL",
    "MANAGED_EVIDENCE_READ_ONLY",
    "SELF_HOSTED_ETCD_DATA_PLANE",
    "SELF_HOSTED_TRANSIT_SIGN",
    "SELF_HOSTED_EXTERNAL_WITNESS",
    "SELF_HOSTED_LAB_FAULT_CONTROL",
    "SELF_HOSTED_EVIDENCE_READ_ONLY",
]
EXPECTED_ADAPTER_CATALOG: dict[str, dict[str, Any]] = {
    "SPANNER_AUTHORITY_ADAPTER": {
        "allowed_operations": [
            "RUN_EXPLICIT_SERIALIZABLE_AUTHORITY_TRANSACTION",
            "STRONG_READ_EXACT_OPERATION_KEY",
            "CAS_ABSENT_TO_TERMINAL_FENCE",
            "PERSIST_PREPARED_ATTEMPT",
            "PERSIST_VALIDATED_RECEIPT",
            "QUARANTINE_ATTEMPT",
        ],
        "credential_class": "MANAGED_SPANNER_DATA_PLANE",
        "evidence_returns": [
            "REQUESTED_AND_EFFECTIVE_ISOLATION",
            "CLOSURE_ATTEMPT_RECEIPTS",
            "EXACT_RECORD_AND_REVISION",
            "TOP_LEVEL_COMMIT_OR_UNKNOWN_RECEIPT",
        ],
        "forbidden_operations": [
            "EXTERNAL_SIDE_EFFECT_INSIDE_RETRYABLE_CLOSURE",
            "NON_SERIALIZABLE_AUTHORITY_TRANSACTION",
        ],
        "retry_rule": "DATABASE_CLOSURE_RETRIES_OBSERVED_WITH_STABLE_INPUTS",
    },
    "CLOUD_KMS_SIGNER_ADAPTER": {
        "allowed_operations": [
            "SIGN_EXACT_137_RAW_BYTES_WITH_EXACT_VERSION",
            "RETURN_OPERATION_SPECIFIC_RESPONSE_EVIDENCE",
        ],
        "credential_class": "MANAGED_KMS_SIGN",
        "evidence_returns": [
            "APPLICATION_CALL_RECEIPT",
            "REQUEST_AND_RESPONSE_SHA256",
            "VERSION_PROTECTION_CRC_AND_VERIFICATION_FIELDS",
        ],
        "forbidden_operations": [
            "DIGEST_ARM_SIGNING",
            "IMPLICIT_OR_PARENT_KEY_VERSION",
            "HIDDEN_TRANSPORT_RETRY",
        ],
        "retry_rule": "ZERO_HIDDEN_SIGNER_RETRIES",
    },
    "MANAGED_FAULT_PROXY_ADAPTER": {
        "allowed_operations": [
            "ARM_EXACT_ASSIGNED_CUT",
            "TRIGGER_ONCE_FOR_EXACT_RUN_TRAFFIC",
            "RECORD_WIRE_ATTEMPTS_WITHOUT_PROCESSING_CLAIM",
        ],
        "credential_class": "MANAGED_FAULT_PROXY_CONTROL",
        "evidence_returns": ["ARM_RECEIPT", "TRIGGER_RECEIPT", "CAUSAL_BINDING_SHA256", "WIRE_ATTEMPT_INDEX"],
        "forbidden_operations": ["CROSS_NAMESPACE_FAULT", "MULTIPLE_TRIGGER", "PROVIDER_PROCESSING_INFERENCE"],
        "retry_rule": "NOT_APPLICABLE",
        "stop_capability_may_authorize_experiment": False,
        "stop_only_credential_class": "STOP_FAULT_DISARM_EGRESS_CONTROL",
        "stop_only_evidence_returns": ["DISARM_RECEIPT", "EGRESS_ISOLATION_RECEIPT"],
        "stop_only_operations": ["DISARM_EXACT_ASSIGNED_CUT", "ISOLATE_EXACT_ASSIGNED_RUN_EGRESS"],
    },
    "MANAGED_EVIDENCE_COLLECTOR_ADAPTER": {
        "allowed_operations": [
            "COLLECT_ALLOWLISTED_NON_SECRET_FIELDS",
            "HASH_IMMUTABLE_RAW_EVIDENCE_INDEX",
            "RETURN_OBSERVATIONS_ONLY",
        ],
        "credential_class": "MANAGED_EVIDENCE_READ_ONLY",
        "evidence_returns": ["PROVIDER_PROFILE_SHA256", "RAW_EVIDENCE_INDEX_SHA256", "SAFE_EVENT_TRACE_SHA256"],
        "forbidden_operations": ["CASE_CLASSIFICATION", "CREDENTIAL_MATERIAL_CAPTURE", "OUTPUT_AUTHORIZATION"],
        "retry_rule": "READ_ONLY_COLLECTION_IS_SEPARATELY_ACCOUNTED",
    },
    "ETCD_AUTHORITY_ADAPTER": {
        "allowed_operations": [
            "LINEARIZABLE_EXACT_READ",
            "NON_NESTED_NONLEASED_EXACT_KEY_CAS",
            "CAS_ABSENT_TO_TERMINAL_FENCE",
            "PERSIST_PREPARED_ATTEMPT",
            "PERSIST_VALIDATED_RECEIPT",
            "QUARANTINE_ATTEMPT",
        ],
        "credential_class": "SELF_HOSTED_ETCD_DATA_PLANE",
        "evidence_returns": [
            "SERIALIZABLE_FALSE_REQUEST_FIELD",
            "TOP_LEVEL_TRANSACTION_REVISION",
            "EXACT_RECORD_MOD_REVISION_AND_CAS_RECEIPT",
        ],
        "forbidden_operations": ["SERIALIZABLE_STALE_AUTHORITY_READ", "NESTED_TRANSACTION", "LEASED_AUTHORITY_KEY"],
        "retry_rule": "UNKNOWN_MUTATION_REQUIRES_EXACT_LOOKUP_OR_TERMINAL_FENCE",
    },
    "OPENBAO_TRANSIT_ADAPTER": {
        "allowed_operations": [
            "SIGN_SINGLE_NONBATCH_CONTEXT_FREE_EXACT_137_BYTE_INPUT",
            "RETURN_VERSIONED_SIGNATURE_OBSERVATION",
        ],
        "credential_class": "SELF_HOSTED_TRANSIT_SIGN",
        "evidence_returns": ["APPLICATION_CALL_RECEIPT", "REQUEST_RESPONSE_AND_VERSION_BINDINGS", "ROUTE_AND_REQUEST_IDENTITIES"],
        "forbidden_operations": ["IMPLICIT_LATEST_VERSION", "DERIVED_BATCH_CONTEXT_OR_PREHASH_MODE", "HIDDEN_TRANSPORT_RETRY"],
        "retry_rule": "ZERO_HIDDEN_SIGNER_RETRIES",
    },
    "EXTERNAL_RESTORE_WITNESS_ADAPTER": {
        "allowed_operations": ["CURRENT_LINEARIZABLE_READ", "COMPARE_EXACT_PREVIOUS_HASH_AND_GENERATION_THEN_PUT"],
        "credential_class": "SELF_HOSTED_EXTERNAL_WITNESS",
        "evidence_returns": ["FIFTEEN_FIELD_WITNESS_RECORD", "WITNESS_KEY_HASH_GENERATION_AND_CAS_RECEIPT"],
        "forbidden_operations": ["SHARED_RESTORE_ACTOR_CREDENTIAL", "WITNESS_INSIDE_ETCD_SNAPSHOT_OR_RESTORE_DOMAIN"],
        "retry_rule": "CONFLICT_OR_UNAVAILABILITY_INCIDENT_QUARANTINES",
    },
    "LAB_FAULT_CONTROLLER_ADAPTER": {
        "allowed_operations": [
            "ARM_EXACT_ASSIGNED_LAB_CUT",
            "TRIGGER_ONCE_INSIDE_EXACT_RUN_NAMESPACE",
            "RECORD_TOPOLOGY_AND_CAUSAL_BINDING",
        ],
        "credential_class": "SELF_HOSTED_LAB_FAULT_CONTROL",
        "evidence_returns": ["ARM_RECEIPT", "TRIGGER_RECEIPT", "TOPOLOGY_SHA256", "CAUSAL_BINDING_SHA256"],
        "forbidden_operations": ["CROSS_RUN_OR_CROSS_TRACK_FAULT", "MULTIPLE_TRIGGER", "UNSCOPED_RESTORE_OR_SEAL_ACTION"],
        "retry_rule": "NOT_APPLICABLE",
        "stop_capability_may_authorize_experiment": False,
        "stop_only_credential_class": "STOP_FAULT_DISARM_EGRESS_CONTROL",
        "stop_only_evidence_returns": ["DISARM_RECEIPT", "EGRESS_ISOLATION_RECEIPT"],
        "stop_only_operations": ["DISARM_EXACT_ASSIGNED_CUT", "ISOLATE_EXACT_ASSIGNED_RUN_EGRESS"],
    },
    "SELF_HOSTED_EVIDENCE_COLLECTOR_ADAPTER": {
        "allowed_operations": [
            "COLLECT_ALLOWLISTED_NON_SECRET_FIELDS",
            "HASH_IMMUTABLE_LAB_EVIDENCE_INDEX",
            "CORRELATE_ROUTE_EXECUTOR_AUDIT_AND_WIRE_IDENTITIES",
            "RETURN_OBSERVATIONS_ONLY",
        ],
        "credential_class": "SELF_HOSTED_EVIDENCE_READ_ONLY",
        "evidence_returns": ["PROVIDER_PROFILE_SHA256", "RAW_EVIDENCE_INDEX_SHA256", "SAFE_EVENT_TRACE_SHA256"],
        "forbidden_operations": ["CASE_CLASSIFICATION", "CREDENTIAL_MATERIAL_CAPTURE", "OUTPUT_AUTHORIZATION"],
        "retry_rule": "READ_ONLY_COLLECTION_IS_SEPARATELY_ACCOUNTED",
    },
}
EXPECTED_CLIENT_CASES = [
    "M02",
    "M03",
    "M05",
    "M06",
    "M07",
    "M08",
    "M09",
    "M10",
    "M11",
    "S02",
    "S03",
    "S08",
    "S16",
    "S17",
]
EXPECTED_MANAGED_PROVIDER_CASES = ["M00", "M01", "M04", "M12", "M13", "M14", "M15"]
EXPECTED_SELF_HOSTED_LAB_CASES = [
    "S00",
    "S01",
    "S04",
    "S05",
    "S06",
    "S07",
    "S09",
    "S10",
    "S11",
    "S12",
    "S13",
    "S14",
    "S15",
]
EXPECTED_BOUNDARY = {
    "adapter_implementation_present": False,
    "authority_receipts_bound": False,
    "condition_output_authorized": False,
    "cost_authority_bound": False,
    "credentials_accessed": False,
    "experiment_executed": False,
    "live_endpoint_bound": False,
    "live_generator_in_scope": False,
    "live_output_permit_defined": False,
    "paid_resources_provisioned": False,
    "production_adapter_in_scope": False,
    "provider_called": False,
    "provider_profile_bound": False,
    "receipt_is_output_permit": False,
    "secret_material_present": False,
    "side_effects_unlocked": "NONE",
    "synthetic_authority_present": False,
}
EXPECTED_OBSERVATION_BOUNDARY = {
    "adapter_implemented": False,
    "condition_output_authorized": False,
    "cost_authority_bound": False,
    "credentials_accessed": False,
    "execution_capability_emitted": False,
    "experiment_executed": False,
    "paid_resources_provisioned": False,
    "production_adapter_in_scope": False,
    "provider_called": False,
    "receipt_is_execution_authority": False,
    "receipt_is_output_permit": False,
    "runner_implemented": False,
    "side_effects_unlocked": "NONE",
    "stop_capability_emitted": False,
}


def _validate_contract_identity(contract: dict[str, Any]) -> None:
    exact_keys(contract, EXPECTED_TOP_LEVEL_KEYS, "E_CONTRACT_FIELDS", "adapter contract")
    require(contract["schema"] == CONTRACT_SCHEMA, "E_CONTRACT_SCHEMA", "contract schema mismatch")
    require(contract["version"] == 1, "E_CONTRACT_VERSION", "contract version mismatch")
    require(contract["baseline_commit"] == BASELINE_COMMIT, "E_CONTRACT_BASELINE", "baseline mismatch")
    require(contract["date"] == "2026-07-15", "E_CONTRACT_DATE", "date mismatch")
    require(contract["status"] == STATUS, "E_CONTRACT_STATUS", "contract status mismatch")
    require(contract["decision"] == DECISION, "E_CONTRACT_DECISION", "contract decision mismatch")
    require(contract["next_unit"] == NEXT_UNIT, "E_CONTRACT_NEXT", "next unit mismatch")
    require(
        contract["purpose"]
        == "FREEZE_NON_AUTHORIZING_RUNNER_AUTHORITY_ADAPTER_EVIDENCE_STOP_AND_RECOVERY_SEMANTICS_WITHOUT_PROVIDER_OR_CREDENTIAL_ACCESS",
        "E_CONTRACT_PURPOSE",
        "purpose mismatch",
    )


def _validate_authority_model(contract: dict[str, Any]) -> None:
    model = contract["authority_model"]
    exact_keys(
        model,
        ("artifact_count", "artifacts", "binding_fields", "capability", "currentness_formula", "emergency_stop_scope", "intersection_formula", "phase_operation_catalog", "phase_order", "phases", "track_grain", "wildcard_or_parent_resource_scope_allowed"),
        "E_AUTHORITY_MODEL_FIELDS",
        "authority model",
    )
    require(model["artifact_count"] == 5, "E_AUTHORITY_COUNT", "authority artifact count must be five")
    require_equal(model["artifacts"], EXPECTED_AUTHORITY_ARTIFACTS, "E_AUTHORITY_ARTIFACTS", "authority artifacts")
    require_equal(model["binding_fields"], EXPECTED_AUTHORITY_BINDING_FIELDS, "E_AUTHORITY_BINDINGS", "authority binding fields")
    require_equal(model["phase_order"], ["PREFLIGHT_OBSERVATION", "EXPERIMENT_EXECUTION"], "E_AUTHORITY_PHASES", "phase order")
    require(set(model["phases"]) == {"PREFLIGHT_OBSERVATION", "EXPERIMENT_EXECUTION"}, "E_AUTHORITY_PHASES", "phase catalog mismatch")
    preflight = model["phases"]["PREFLIGHT_OBSERVATION"]
    require_equal(
        preflight,
        {
            "allowed_actions": "EXACT_READ_ONLY_METADATA_AND_PROFILE_OBSERVATION_ONLY",
            "forbidden_actions": "SIGN_MUTATE_FAULT_PROVISION_OR_START_LAB",
            "scope": "ONE_TRACK_ONE_ASSIGNED_RUN_EXACT_RESOURCE_COMMITMENT_DISTINCT_FROM_AND_NOT_REUSABLE_AS_EXECUTION_AUTHORITY",
        },
        "E_AUTHORITY_PREFLIGHT",
        "preflight phase",
    )
    execution = model["phases"]["EXPERIMENT_EXECUTION"]
    require_equal(
        execution,
        {
            "allowed_actions": "EXACT_TRACK_CASE_SCHEDULE_AND_ADAPTER_ACTIONS_ONLY",
            "prerequisites": "FROZEN_CURRENT_PROFILE_CONFIGURATION_SCHEDULE_RUNNER_ADAPTER_SET_ASSIGNMENT_AND_ALL_FIVE_CURRENT_EXECUTION_AUTHORITY_ARTIFACTS",
            "scope": "ONE_TRACK_ONE_ASSIGNED_RUN",
        },
        "E_AUTHORITY_EXECUTION",
        "execution phase",
    )
    require(model["track_grain"] == "SEPARATE_NON_SUBSTITUTABLE_AUTHORITY_BUNDLE_PER_TRACK", "E_AUTHORITY_TRACK", "track authority grain mismatch")
    require(model["wildcard_or_parent_resource_scope_allowed"] is False, "E_AUTHORITY_SCOPE", "wildcard/parent scope must be forbidden")
    require_equal(
        model["capability"],
        {
            "assignment_and_namespace_bound": True,
            "credential_material_embedded": False,
            "cross_run_reuse_allowed": False,
            "cross_track_reuse_allowed": False,
            "kind": "OPAQUE_NON_SERIALIZABLE_PROCESS_LOCAL_SINGLE_USE",
            "persistence_allowed": False,
            "phase_bound": True,
            "receipt_or_capability_is_output_permit": False,
            "serialization_allowed": False,
            "stop_invalidates_immediately": True,
        },
        "E_AUTHORITY_CAPABILITY",
        "authority capability",
    )
    require_equal(
        model["intersection_formula"],
        {
            "case_ids": "SET_INTERSECTION_OF_OWNER_CUSTODIAN_RESOURCE_AND_COST_ALLOWED_CASE_IDS_WITH_EMERGENCY_SCOPE_REQUIRED_TO_BIND_THE_SAME_ASSIGNED_RUN",
            "digest_scopes": "RESOURCE_CREDENTIAL_COST_RETENTION_AND_CLEANUP_SCOPE_HASHES_MUST_EACH_EXACTLY_MATCH_ACROSS_ALL_FIVE_RECEIPTS_AND_AUTHORITY_INTERSECTION",
            "emergency_authority_algebra": "EMERGENCY_STOP_AUTHORITY_IS_A_REQUIRED_CURRENT_VETO_AND_REDUCTIVE_CAPABILITY_NEVER_A_POSITIVE_EXECUTION_GRANT; ITS_FORBIDDEN_OPERATIONS_PARTICIPATE_BUT ITS_ALLOWED_OPERATIONS_DO_NOT_ADD_OR_INTERSECT_POSITIVE_EXECUTION_AUTHORITY",
            "execution_assignment_rule": "EFFECTIVE_CASE_AND_REPETITION_ARE_SINGLETON_AND_EQUAL_THE_FROZEN_ASSIGNMENT_CASE_AND_REPETITION",
            "field_level_intersection_sha256": "FRAMED_SHA256_OF_AUTHORITY_INTERSECTION_DOMAIN_UTF8_AND_AB_CANONICAL_JSON_V1_COMPLETE_AUTHORITY_INTERSECTION_BYTES_WITH_FIELD_LEVEL_INTERSECTION_SHA256_OMITTED",
            "operations": "SET_INTERSECTION_OF_OWNER_CUSTODIAN_RESOURCE_AND_COST_ALLOWED_OPERATIONS_MINUS_SET_UNION_OF_ALL_FIVE_FORBIDDEN_OPERATIONS",
            "repetition_indices": "SET_INTERSECTION_OF_OWNER_CUSTODIAN_RESOURCE_AND_COST_ALLOWED_REPETITION_INDICES_WITH_EMERGENCY_SCOPE_REQUIRED_TO_BIND_THE_SAME_ASSIGNED_RUN",
            "required_nonempty": True,
        },
        "E_AUTHORITY_INTERSECTION_FORMULA",
        "authority intersection formula",
    )
    require_equal(
        model["currentness_formula"],
        {
            "binding_equality": "ROOT_INTERSECTION_CAPABILITY_AND_ALL_FIVE_RECEIPTS_EXACTLY_MATCH_TRACK_PHASE_SUITE_SIMULATION_RUN_NAMESPACE_ASSIGNMENT_CONTRACT_HARNESS_PROFILE_CONFIGURATION_SCHEDULE_RUNNER_ADAPTER_ADAPTER_SET_STOP_CONTROL_PLANE_RESOURCE_CREDENTIAL_COST_RETENTION_CLEANUP_AND_REVOCATION_EPOCH_BINDINGS; ROOT_INTERSECTION_AND_CAPABILITY_EXACTLY_MATCH_FIELD_LEVEL_INTERSECTION_AND_EFFECTIVE_OPERATIONS",
            "checked_at_rule": "ALL_TIMESTAMPS_ARE_STRICT_RFC3339_UTC_SECONDS_CALENDAR_VALID_AND_TRUSTED_CHECKED_AT_UTC_IS_AT_OR_AFTER_EVERY_NOT_BEFORE_UTC_AND_STRICTLY_BEFORE_EVERY_EXPIRES_AT_UTC",
            "evidence_rule": "TRUSTED_TIME_AND_ROW_CURRENTNESS_RECEIPT_HASHES_MUST_RESOLVE_TO_CANONICAL_SIGNED_ALLOWLISTED_CONTROL_PLANE_EVIDENCE_BINDING_CHECKED_AT_TRACK_PHASE_SUITE_RUN_NAMESPACE_ASSIGNMENT_PROFILE_RESOURCE_CREDENTIAL_COST_AND_REVOCATION_EPOCH; BOOLEAN_ASSERTIONS_ALONE_ARE_NOT_EVIDENCE",
            "phase_freshness_rule": "PREFLIGHT_AND_EXECUTION_USE_DISTINCT_REQUEST_NONCE_SIGNATURE_RECEIPT_AND_CAPABILITY_COMMITMENTS",
            "receipt_time_order_rule": "FOR_EACH_RECEIPT_ISSUED_AT_UTC_IS_NOT_AFTER_NOT_BEFORE_UTC_AND_NOT_BEFORE_UTC_IS_STRICTLY_BEFORE_EXPIRES_AT_UTC; SIGNATURE_VERIFIED_AT_UTC_IS_NOT_BEFORE_ISSUED_AT_UTC_AND_NOT_AFTER_TRUSTED_CHECKED_AT_UTC",
            "revocation_rule": "ROOT_CURRENTNESS_AND_ALL_FIVE_RECEIPTS_HAVE_ONE_EQUAL_CURRENT_REVOCATION_EPOCH_AND_NO_REVOCATION_OR_STOP_RECORD_EXISTS",
        },
        "E_AUTHORITY_CURRENTNESS_FORMULA",
        "authority currentness formula",
    )
    require_equal(
        model["phase_operation_catalog"],
        {
            "EXPERIMENT_EXECUTION_GRANT": "EFFECTIVE_OPERATIONS_MUST_BE_A_NONEMPTY_SUBSET_OF_THE_EXACT_ASSIGNED_ROUTE_EXPERIMENT_ADAPTER_ALLOWED_OPERATIONS_AND_MUST_EXCLUDE_STOP_ONLY_OPERATIONS",
            "PREFLIGHT_OBSERVATION_GRANT": [
                "READ_COST_BUDGET_METADATA",
                "READ_CREDENTIAL_LEASE_METADATA",
                "READ_EVIDENCE_SINK_HEALTH",
                "READ_PROVIDER_PROFILE_METADATA",
                "READ_RESOURCE_METADATA",
            ],
        },
        "E_AUTHORITY_PHASE_OPERATIONS",
        "authority phase operation catalog",
    )
    require_equal(
        model["emergency_stop_scope"],
        {
            "allowed_operations": [
                "BLOCK_NEW_CALLS_FOR_EXACT_RUN",
                "CAS_EXACT_RUN_CAPABILITY_TO_STOP_FENCED",
                "CONFIRM_RETENTION_BINDINGS",
                "CONFIRM_ZERO_ACTIVE_LEASE_COMMITMENTS",
                "DISARM_EXACT_ASSIGNED_CUT",
                "FREEZE_EXACT_ASSIGNED_RESOURCES",
                "ISOLATE_EXACT_ASSIGNED_RUN_EGRESS",
                "PERSIST_CURRENT_ROW_DURABLE_STATE_AND_SAFE_EVIDENCE",
                "REDUCTIVE_TEARDOWN_WITHIN_EXACT_CLEANUP_SCOPE",
                "REVOKE_EXACT_RUN_CREDENTIAL_LEASES",
            ],
            "forbidden_operations": [
                "ARM_OR_TRIGGER_FAULT",
                "AUTHORIZE_CONDITION_OUTPUT_OR_OUTPUT_PERMIT",
                "CREATE_OR_EXPAND_RESOURCE_SCOPE",
                "SIGN_PROVIDER_MESSAGE",
                "START_OR_RESUME_EXPERIMENT",
            ],
            "positive_execution_authority_added": False,
        },
        "E_EMERGENCY_SCOPE",
        "emergency stop scope",
    )


def _validate_start_stop(contract: dict[str, Any]) -> None:
    logic = contract["start_stop_logic"]
    exact_keys(logic, ("start", "stop"), "E_START_STOP_FIELDS", "start/stop logic")
    require_equal(
        logic["start"],
        {
            "action": "AFTER_ALL_CONDITIONS_PASS_DURABLY_CAS_THE_EXACT_CAPABILITY_CONTROL_LEDGER_RECORD_FROM_UNUSED_TO_START_COMMITTED_ONCE_AND_ONLY_THEN_RELEASE_THE_PRIVATE_CAPABILITY_TO_THE_BOUND_EXECUTOR_SESSION; CAS_FAILURE_OR_UNKNOWN_OUTCOME_PERMITS_NO_PROVIDER_OR_FAULT_CALL",
            "combination": "AND_ALL_REQUIRED",
            "conditions": EXPECTED_START_CONDITIONS,
        },
        "E_START_LOGIC",
        "start AND gate",
    )
    require_equal(
        logic["stop"],
        {
            "actions": EXPECTED_STOP_ACTIONS,
            "combination": "OR_ANY_TRIGGER",
            "completion_rule": (
                "STOP_ABSORBING_COMPLETE_REQUIRES_CAPABILITY_INVALIDATED_NEW_CALLS_BLOCKED_ROW_AND_EVIDENCE_PRESERVED_"
                "CLEANUP_REDUCTIVE_COMPLETE_CREDENTIAL_REVOKED_FAULT_DISARMED_ZERO_CONTROL_PLANE_FAILURES_ZERO_UNRESOLVED_AMBIGUITIES_AND_DURABLE_RECEIPT; "
                "ALL_OTHER_STATES_HAVE_NULL_STOP_COMPLETION_TIME; "
                "FAILED_QUARANTINED_IS_TERMINAL_ESCALATED_AND_NONCONTINUABLE"
            ),
            "trigger_reason_role_map": EXPECTED_TRIGGER_REASON_ROLE_MAP,
            "triggers": EXPECTED_STOP_TRIGGERS,
        },
        "E_STOP_LOGIC",
        "stop OR gate",
    )
    # Absorption is an independently recomputed consequence: any stop trigger
    # blocks new calls, invalidates the one-shot capability, retains state, and
    # leaves no automatic continuation path.
    require(
        logic["stop"]["combination"] == "OR_ANY_TRIGGER"
        and "BLOCK_NEW_CALLS_AND_INVALIDATE_CAPABILITY" in logic["stop"]["actions"]
        and "RETAIN_CURRENT_ROW_AND_DURABLE_STATE" in logic["stop"]["actions"]
        and contract["authority_model"]["capability"]["stop_invalidates_immediately"] is True,
        "E_STOP_NOT_ABSORBING",
        "stop is not absorbing",
    )


def _validate_adapters(contract: dict[str, Any]) -> None:
    interfaces = contract["adapter_interfaces"]
    exact_keys(interfaces, ("client_conformance_route", "managed", "self_hosted"), "E_ADAPTER_FIELDS", "adapter interfaces")
    require_equal(
        interfaces["client_conformance_route"],
        {
            "adapter_id": "OFFLINE_CLIENT_CONFORMANCE_DOUBLE",
            "case_count": 14,
            "provider_adapter_allowed": False,
            "provider_called": False,
            "row_count": 420,
        },
        "E_CLIENT_ROUTE",
        "client conformance route",
    )
    expected_ids_by_track = {
        "managed": EXPECTED_MANAGED_ADAPTER_IDS,
        "self_hosted": EXPECTED_SELF_HOSTED_ADAPTER_IDS,
    }
    all_ids: list[str] = []
    all_credentials: list[str] = []
    for track, expected_ids in expected_ids_by_track.items():
        section = interfaces[track]
        exact_keys(section, ("adapter_count", "adapters", "composition_rule"), "E_ADAPTER_TRACK_FIELDS", f"{track} adapter section")
        require(section["adapter_count"] == len(expected_ids), "E_ADAPTER_COUNT", f"{track} adapter count mismatch")
        require(type(section["adapters"]) is list and len(section["adapters"]) == len(expected_ids), "E_ADAPTER_COUNT", f"{track} adapter list mismatch")
        actual_ids: list[str] = []
        for index, adapter in enumerate(section["adapters"]):
            require(type(adapter["adapter_id"]) is str, "E_ADAPTER_ID", "adapter id must be a string")
            expected_catalog_entry = EXPECTED_ADAPTER_CATALOG.get(adapter["adapter_id"])
            require(expected_catalog_entry is not None, "E_ADAPTER_CATALOG", f"unknown adapter {adapter['adapter_id']}")
            exact_keys(adapter, ("adapter_id", *expected_catalog_entry), "E_ADAPTER_SHAPE", f"{track} adapter {index}")
            require(type(adapter["credential_class"]) is str, "E_ADAPTER_CREDENTIAL", "credential class must be a string")
            for field in ("allowed_operations", "evidence_returns", "forbidden_operations"):
                require(type(adapter[field]) is list and adapter[field], "E_ADAPTER_SHAPE", f"{adapter['adapter_id']} {field} missing")
                require(all(type(item) is str for item in adapter[field]), "E_ADAPTER_SHAPE", f"{adapter['adapter_id']} {field} type drift")
                require(len(adapter[field]) == len(set(adapter[field])), "E_ADAPTER_SHAPE", f"{adapter['adapter_id']} {field} duplicates")
            actual_ids.append(adapter["adapter_id"])
            all_ids.append(adapter["adapter_id"])
            all_credentials.append(adapter["credential_class"])
            require_equal(
                {key: adapter[key] for key in expected_catalog_entry},
                expected_catalog_entry,
                "E_ADAPTER_CATALOG",
                f"{adapter['adapter_id']} full operation/evidence catalog",
            )
        require_equal(actual_ids, expected_ids, "E_ADAPTER_IDS", f"{track} adapter ids")
    require(len(all_ids) == len(set(all_ids)) == 9, "E_ADAPTER_ID", "adapter ids must be distinct")
    require_equal(all_credentials, EXPECTED_CREDENTIAL_CLASSES, "E_ADAPTER_CREDENTIAL", "adapter credential classes")
    require(interfaces["managed"]["composition_rule"] == "FOUR_SEPARATE_LEAST_PRIVILEGE_INTERFACES_NO_SHARED_OMNIPOTENT_ADAPTER", "E_ADAPTER_COMPOSITION", "managed composition is not separated")
    require(interfaces["self_hosted"]["composition_rule"] == "FIVE_SEPARATE_LEAST_PRIVILEGE_INTERFACES_NO_SHARED_OMNIPOTENT_ADAPTER", "E_ADAPTER_COMPOSITION", "self-hosted composition is not separated")
    for section in (interfaces["managed"], interfaces["self_hosted"]):
        for adapter in section["adapters"]:
            if adapter["adapter_id"].endswith("EVIDENCE_COLLECTOR_ADAPTER"):
                require("CASE_CLASSIFICATION" in adapter["forbidden_operations"], "E_ADAPTER_CLASSIFICATION", "evidence adapter may classify")
                require("OUTPUT_AUTHORIZATION" in adapter["forbidden_operations"], "E_ADAPTER_CLASSIFICATION", "evidence adapter may authorize output")
            if "SIGNER_ADAPTER" in adapter["adapter_id"] or "TRANSIT_ADAPTER" in adapter["adapter_id"]:
                require("ZERO_HIDDEN_SIGNER_RETRIES" == adapter["retry_rule"], "E_ADAPTER_HIDDEN_RETRY", "signer hidden retry rule drift")
                require("HIDDEN_TRANSPORT_RETRY" in adapter["forbidden_operations"], "E_ADAPTER_HIDDEN_RETRY", "hidden retry not forbidden")
    witness = next(adapter for adapter in interfaces["self_hosted"]["adapters"] if adapter["adapter_id"] == "EXTERNAL_RESTORE_WITNESS_ADAPTER")
    require("WITNESS_INSIDE_ETCD_SNAPSHOT_OR_RESTORE_DOMAIN" in witness["forbidden_operations"], "E_WITNESS_DOMAIN", "witness independence missing")


def _validate_routing(contract: dict[str, Any]) -> None:
    plan = contract["execution_plan"]
    exact_keys(plan, ("assignment_order", "case_routing", "counts", "track_interleaving_allowed"), "E_EXECUTION_PLAN_FIELDS", "execution plan")
    require(plan["assignment_order"] == "CONFIGURATION_AND_PROFILE_FROZEN_THEN_SCHEDULE_SEALED_THEN_PER_RUN_CURRENTNESS_THEN_ARM_THEN_START", "E_ASSIGNMENT_ORDER", "assignment order mismatch")
    require(plan["track_interleaving_allowed"] is False, "E_TRACK_INTERLEAVING", "track interleaving must be false")
    expected_routes = {
        "CLIENT_CONFORMANCE_DOUBLE": (EXPECTED_CLIENT_CASES, 420),
        "MANAGED_SERVICE_WITH_CLIENT_FAULT_PROXY": (EXPECTED_MANAGED_PROVIDER_CASES, 210),
        "SELF_HOSTED_ADVERSARIAL_LAB": (EXPECTED_SELF_HOSTED_LAB_CASES, 390),
    }
    require(set(plan["case_routing"]) == set(expected_routes), "E_LOCUS_CATALOG", "locus catalog mismatch")
    routed: list[str] = []
    for locus, (expected_cases, expected_rows) in expected_routes.items():
        route = plan["case_routing"][locus]
        require_equal(route, {"case_ids": expected_cases, "rows": expected_rows}, "E_LOCUS_ROUTE", f"{locus} route")
        require(route["rows"] == len(route["case_ids"]) * 30, "E_LOCUS_ROWS", f"{locus} row arithmetic mismatch")
        routed.extend(route["case_ids"])
    expected_all = {f"M{index:02d}" for index in range(16)} | {f"S{index:02d}" for index in range(18)}
    require(set(routed) == expected_all and len(routed) == len(set(routed)) == 34, "E_LOCUS_PARTITION", "case routing is not an exact partition")
    require_equal(
        plan["counts"],
        {
            "cases": 34,
            "client_conformance_double_rows": 420,
            "managed_service_fault_proxy_rows": 210,
            "planned_rows": 1020,
            "repetitions_per_case": 30,
            "self_hosted_adversarial_lab_rows": 390,
            "tracks": 2,
        },
        "E_EXECUTION_COUNTS",
        "execution counts",
    )
    require(sum(plan["case_routing"][locus]["rows"] for locus in expected_routes) == 1020, "E_EXECUTION_COUNTS", "locus totals do not equal 1020")


def _validate_acceptance_evidence_retention(contract: dict[str, Any]) -> None:
    require_equal(
        contract["acceptance_policy"],
        {
            "adapter_classification_forbidden": True,
            "all_assigned_rows_retained": True,
            "authority_scope_must_be_exact_subset": True,
            "cross_track_capability_reuse_forbidden": True,
            "hidden_signer_retries_forbidden": True,
            "post_outcome_exclusion_forbidden": True,
            "provider_processing_inference_forbidden": True,
            "runtime_result_requires_all_thirty_rows_per_case": True,
            "track_comparison_allowed": False,
        },
        "E_ACCEPTANCE_POLICY",
        "acceptance policy",
    )
    evidence = contract["evidence_contract"]
    require_equal(
        evidence,
        {
            "actual_evidence_origins": [
                "RUNTIME_CLIENT_CONFORMANCE_DOUBLE",
                "MANAGED_SERVICE_WITH_CLIENT_FAULT_PROXY",
                "SELF_HOSTED_ADVERSARIAL_LAB",
            ],
            "adapter_may_return_case_classification": False,
            "causal_order_rule": "MONOTONIC_RUN_SEQUENCE_AND_HASH_BINDINGS_NOT_CROSS_SYSTEM_WALL_CLOCK_INFERENCE",
            "counter_fields": [
                "APPLICATION_CALL_COUNT",
                "WIRE_ATTEMPT_COUNT",
                "PROVIDER_PROCESSING_COUNT_NULL_UNLESS_INDEPENDENTLY_EVIDENCED",
            ],
            "eligibility_rules": [
                "ACTUAL_ORIGIN_EQUALS_PLANNED_EVIDENCE_LOCUS",
                "AUTHORITY_ASSIGNMENT_PROFILE_CONFIGURATION_SCHEDULE_RUNNER_ADAPTER_ADAPTER_SET_AND_STOP_CONTROL_PLANE_HASHES_MATCH",
                "ALL_RAW_SAFE_EVIDENCE_HASHES_RESOLVE",
                "NO_RESOURCE_CREDENTIAL_COST_OR_FAULT_SCOPE_BREACH",
                "ASSIGNMENT_PRECEDES_ARM_AND_ARM_PRECEDES_CANDIDATE_START",
                "FAULT_TRIGGER_CARDINALITY_MATCHES_CASE",
                "ADAPTER_RETURN_CONTAINS_OBSERVATIONS_ONLY",
                "NO_PROVIDER_PROCESSING_OR_EXACTLY_ONCE_OVERCLAIM",
            ],
            "envelope_required_fields": [
                "TRACK_CASE_REPETITION_RUN_AND_NAMESPACE",
                "ASSIGNMENT_CONFIGURATION_PROFILE_AUTHORITY_CURRENTNESS_RUNNER_ADAPTER_AND_ADAPTER_SET_SHA256",
                "PLANNED_LOCUS_ACTUAL_ORIGIN_AND_ELIGIBILITY",
                "PRE_AND_POST_DURABLE_STATE_SHA256",
                "NINETEEN_FIELD_OPERATION_RECORD_AND_SIXTEEN_FIELD_CAS_ENVELOPE",
                "PREPARED_CALL_VALIDATION_AND_RECEIPT_BINDING_SHA256",
                "FAULT_ARM_TRIGGER_CUT_VARIANT_AND_CAUSAL_BINDING",
                "REQUEST_RESPONSE_PROVIDER_AUDIT_AND_EVENT_INDEX_SHA256",
                "CREDENTIAL_RESOURCE_COST_STOP_CLEANUP_AND_RETENTION_RECEIPTS",
                "ZERO_OUTPUT_AND_NO_PERMIT_ASSERTIONS",
            ],
            "provider_evidence_hash_does_not_imply_provider_processing": True,
            "raw_capture_rule": "ALLOWLISTED_NON_SECRET_PROTOCOL_FIELDS_ONLY_RAW_SECRET_BEARING_MATERIAL_FORBIDDEN",
        },
        "E_EVIDENCE_CONTRACT",
        "evidence contract",
    )
    retained = contract["retained_row_contract"]
    require_equal(
        retained,
        {
            "case_classification_null_for_nonevaluable_row": True,
            "counts_toward_acceptance_evidence_rule": "ONLY_COMPLETED_EVALUABLE_ROW_WITH_ELIGIBLE_MATCHING_LOCUS_EVIDENCE",
            "counts_toward_denominator_rule": "EVERY_ASSIGNED_RUNTIME_ATTEMPT_INCLUDING_FAILURE_ABORT_AND_STOP",
            "outcomes": [
                "EXPERIMENT_COMPLETED_EVALUABLE",
                "EXPERIMENT_INFRASTRUCTURE_FAILURE_RETAINED",
                "EXPERIMENT_BOUNDARY_BREACH_RETAINED",
                "EXPERIMENT_OPERATOR_STOP_RETAINED",
            ],
            "provider_called_may_be_false_for_valid_experimental_row": True,
            "retained": True,
            "terminal_ambiguity_may_be_valid_case_classification": True,
        },
        "E_RETAINED_ROW",
        "retained row contract",
    )
    s12 = contract["s12_branch_contract"]
    require_equal(
        s12,
        {
            "correlated_postwire_failure_branch": {
                "allowed_classification": "FAIL_CLOSED_REJECTED",
                "branch_id": "CORRELATED_POSTWIRE_FAIL_CLOSED_REJECTED",
                "requirements": [
                    "TARGET_ROUTE_EXECUTING_OR_REJECTING_NODE_CLUSTER_REQUEST_REDIRECT_FORWARD_AND_WIRE_BOUND",
                    "AUDIT_OR_TRANSPORT_REJECTION_RECEIPT_AND_EXPLICIT_FAIL_CLOSED_REJECTION",
                    "ZERO_ACCEPTED_SIGNATURE_RECEIPT_AND_ZERO_OUTPUT",
                ],
            },
            "failure_branch": {
                "branch_id": "FAIL_CLOSED_PREWIRE_NO_EXECUTOR_CLAIM",
                "requirements": [
                    "TARGET_AND_ROUTE_IDENTITIES_RETAINED",
                    "EXECUTOR_HA_ROLE_REDIRECT_FORWARD_AUDIT_AND_WIRE_ATTEMPT_ARE_NULL",
                    "ZERO_ACCEPTED_RECEIPT_AND_ZERO_OUTPUT",
                ],
            },
            "postwire_uncorrelated_rule": "RETAIN_AS_EXPERIMENT_INFRASTRUCTURE_FAILURE_NOT_CASE_CLASSIFICATION",
            "success_branch": {
                "branch_id": "SUCCESSOR_EXECUTOR_CORRELATED_AND_FULLY_VALIDATED",
                "requirements": [
                    "TARGET_ROUTE_EXECUTOR_HA_ROLE_CLUSTER_REQUEST_REDIRECT_FORWARD_AUDIT_AND_WIRE_BOUND",
                    "SEALED_TARGET_DID_NOT_EXECUTE",
                    "FULL_EXACT_VERSION_MESSAGE_KEY_AND_SIGNATURE_VALIDATION",
                    "DURABLE_RECEIPT_AND_ZERO_OUTPUT",
                ],
            },
        },
        "E_S12_BRANCH",
        "S12 three-result contract",
    )


def _validate_credentials_recovery_boundary(contract: dict[str, Any]) -> None:
    isolation = contract["credential_isolation"]
    exact_keys(
        isolation,
        (
            "ambient_or_default_credential_chain_allowed",
            "broker_activity_separately_evidenced",
            "credential_classes",
            "credential_material_in_artifact_log_cli_or_environment_allowed",
            "cross_adapter_handle_reuse_allowed",
            "emergency_revoke_and_cleanup_capability_separate",
            "evidence_fields",
            "opaque_handle_only",
            "runner_secret_visibility_allowed",
            "stop_control_credential_classes",
            "stop_control_handles_reusable_for_experiment",
        ),
        "E_CREDENTIAL_FIELDS",
        "credential isolation",
    )
    require(isolation["ambient_or_default_credential_chain_allowed"] is False, "E_AMBIENT_CREDENTIAL", "ambient credentials allowed")
    require(isolation["credential_material_in_artifact_log_cli_or_environment_allowed"] is False, "E_CREDENTIAL_EXPOSURE", "credential material exposure allowed")
    require(isolation["cross_adapter_handle_reuse_allowed"] is False, "E_CREDENTIAL_REUSE", "cross-adapter handle reuse allowed")
    require(isolation["runner_secret_visibility_allowed"] is False, "E_CREDENTIAL_VISIBILITY", "runner secret visibility allowed")
    require(isolation["stop_control_handles_reusable_for_experiment"] is False, "E_CREDENTIAL_REUSE", "stop control handle reusable for experiment")
    require(isolation["opaque_handle_only"] is True and isolation["broker_activity_separately_evidenced"] is True and isolation["emergency_revoke_and_cleanup_capability_separate"] is True, "E_CREDENTIAL_HANDLE", "opaque brokered handle model drift")
    require_equal(isolation["credential_classes"], EXPECTED_CREDENTIAL_CLASSES, "E_CREDENTIAL_CLASSES", "credential classes")
    require_equal(
        isolation["evidence_fields"],
        [
            "LEASE_ID_SHA256",
            "ISSUER_AND_AUDIENCE_COMMITMENT_SHA256",
            "PRINCIPAL_COMMITMENT_SHA256",
            "ALLOWED_METHOD_AND_RESOURCE_SCOPE_SHA256",
            "LEASE_CURRENTNESS_RECEIPT_SHA256",
            "USE_COUNT",
            "REVOCATION_RECEIPT_SHA256",
        ],
        "E_CREDENTIAL_EVIDENCE",
        "credential evidence fields",
    )
    require_equal(
        isolation["stop_control_credential_classes"],
        [
            "STOP_CAPABILITY_FENCE_CONTROL",
            "STOP_FAULT_DISARM_EGRESS_CONTROL",
            "STOP_CREDENTIAL_REVOCATION_CONTROL",
            "STOP_DURABLE_EVIDENCE_RETENTION_CONTROL",
            "STOP_SCOPED_RESOURCE_CLEANUP_CONTROL",
        ],
        "E_STOP_CONTROL_CREDENTIALS",
        "stop-control credential classes",
    )
    require_equal(contract["boundary"], EXPECTED_BOUNDARY, "E_BOUNDARY", "contract boundary")
    recovery = contract["recovery_protocol"]
    require(recovery["cleanup_capability_rule"] == "SEPARATE_MONOTONICALLY_REDUCING_REVOKE_ISOLATE_PRESERVE_AND_TEARDOWN_SCOPE_ONLY", "E_CLEANUP_SCOPE", "cleanup capability is not reductive")
    require_equal(
        recovery["durable_runner_states"],
        [
            "ASSIGNED",
            "PREFLIGHT_PASSED",
            "CAPABILITY_ISSUED",
            "FAULT_ARMED",
            "CANDIDATE_STARTED",
            "ATTEMPT_PREPARED",
            "CALL_CONSUMED",
            "RESPONSE_OBSERVED",
            "RESPONSE_VALIDATED",
            "RECEIPT_COMMITTED",
            "AMBIGUOUS_QUARANTINED",
            "ROW_RETAINED",
            "STOP_REQUESTED",
            "STOP_FENCING",
            "STOP_ABSORBING_COMPLETE",
            "STOP_FAILED_QUARANTINED",
        ],
        "E_RECOVERY_STATES",
        "durable runner states",
    )
    require_equal(
        recovery["restart_rules"],
        [
            "SCHEDULE_RUN_ID_NAMESPACE_AND_ASSIGNMENT_NEVER_REGENERATE_OR_SUBSTITUTE",
            "UNSTARTED_ROW_REQUIRES_FRESH_AUTHORITY_CURRENTNESS_AND_START_AND_GATE",
            "PREPARED_CONSUMED_AMBIGUOUS_OR_UNRESOLVED_ATTEMPT_NEVER_REISSUES_SIGNING",
            "UNKNOWN_DATABASE_OR_ETCD_MUTATION_RESOLVES_ONLY_BY_EXACT_READ_OR_TERMINAL_FENCE",
            "NEXT_SCHEDULE_ENTRY_REQUIRES_CURRENT_ENTRY_TERMINAL_RETAINED_RECEIPT",
            "EVIDENCE_PERSIST_FAILURE_STOPS_AND_QUARANTINES",
            "STOP_REQUESTED_OR_LATER_NEVER_RETURNS_TO_AN_EXECUTABLE_STATE_AND_RESTART_CAN_ONLY_CONTINUE_REDUCTIVE_STOP_CONTROL",
        ],
        "E_RECOVERY_RULES",
        "restart rules",
    )


def _validate_predecessor_lineage(contract: dict[str, Any]) -> None:
    require_equal(
        contract["predecessor"],
        {
            "offline_configuration_sha256": EXPECTED_LINEAGE["offline_configuration_sha256"],
            "offline_harness_integration_commit": BASELINE_COMMIT,
            "offline_harness_manifest_sha256": EXPECTED_LINEAGE["offline_harness_manifest_sha256"],
            "offline_harness_source_commit": PREDECESSOR_SOURCE_COMMIT,
            "offline_rows_sha256": EXPECTED_LINEAGE["offline_rows_sha256"],
            "offline_schedule_sha256": EXPECTED_LINEAGE["offline_schedule_sha256"],
            "preregistration_contract_sha256": EXPECTED_LINEAGE["preregistration_contract_sha256"],
        },
        "E_CONTRACT_LINEAGE",
        "contract predecessor lineage",
    )


def _validate_authority_integrity(contract: dict[str, Any]) -> None:
    require_equal(
        contract["authority_integrity"],
        {
            "artifact_role_map": {
                "COST_AUTHORITY_RECEIPT": "COST_CONTROLLER",
                "CUSTODIAN_CREDENTIAL_RECEIPT": "CUSTODIAN",
                "EMERGENCY_STOP_AUTHORITY_RECEIPT": "EMERGENCY_STOP_CONTROLLER",
                "OWNER_SCOPE_RECEIPT": "OWNER",
                "RESOURCE_AUTHORITY_RECEIPT": "RESOURCE_CONTROLLER",
            },
            "assignment_lineage_rule": "RECOMPUTE_THE_FROZEN_PREDECESSOR_OFFLINE_HARNESS_V1_ASSIGNMENT_BLOCK_HASH_SIMULATION_RUN_ID_AND_NAMESPACE_ID_AND_REQUIRE_CASE_REPETITION_CONFIGURATION_TRACK_AND_BLOCK_MEMBERSHIP_TO_MATCH_THE_EXACT_SCHEDULE_ENTRY",
            "assignment_sha256_rule": "SHA256_OF_AB_CANONICAL_JSON_V1_OBJECT_WITH_DOMAIN_SCHEDULE_DOMAIN_TRACK_ID_REPETITION_INDEX_ORDERED_CASE_IDS_CONFIGURATION_SHA256_AND_FROZEN_PREDECESSOR_CONTRACT_SHA256",
            "authorization_request_sha256_preimage": "FRAMED_SHA256_OF_AUTHORIZATION_REQUEST_DOMAIN_UTF8_AND_AB_CANONICAL_JSON_V1_REQUEST_BYTES_WITH_EXACT_TRACK_PHASE_SUITE_RUN_NAMESPACE_ASSIGNMENT_SCOPE_BINDINGS_PRINCIPAL_AND_NONCE",
            "bundle_id_preimage": "FRAMED_SHA256_OF_AUTHORITY_BUNDLE_ID_DOMAIN_UTF8_AND_AB_CANONICAL_JSON_V1_COMPLETE_BUNDLE_BYTES_WITH_BUNDLE_ID_OMITTED",
            "canonicalization": "AB_CANONICAL_JSON_V1_UTF8_SORTED_KEYS_INDENT_2_COLON_SPACE_TRAILING_NEWLINE_ENSURE_ASCII_FALSE_REJECT_DUPLICATE_KEYS_AND_NONFINITE_NUMBERS",
            "capability_commitment_binding_fields": [
                "TRACK_ID",
                "PHASE",
                "SUITE_ID",
                "SIMULATION_RUN_ID",
                "NAMESPACE_ID",
                "ASSIGNMENT_SHA256",
                "CASE_ID",
                "REPETITION_INDEX",
                "CONTRACT_SHA256",
                "RESOURCE_SCOPE_SHA256",
                "CREDENTIAL_SCOPE_SHA256",
                "COST_SCOPE_SHA256",
                "RETENTION_POLICY_SHA256",
                "CLEANUP_POLICY_SHA256",
                "FIELD_LEVEL_INTERSECTION_SHA256",
                "EFFECTIVE_ALLOWED_OPERATIONS",
                "REVOCATION_EPOCH",
                "OFFLINE_HARNESS_MANIFEST_SHA256",
                "PROFILE_SHA256",
                "CONFIGURATION_SHA256",
                "SCHEDULE_SHA256",
                "RUNNER_BUILD_SHA256",
                "ADAPTER_BUILD_SHA256",
                "ADAPTER_SET_MANIFEST_SHA256",
                "STOP_CONTROL_PLANE_MANIFEST_SHA256",
                "CHANNEL_BINDING_SHA256",
                "CONTROL_LEDGER_RECORD_SHA256",
                "SINGLE_CONSUME_TRUE",
                "SINGLE_EXECUTOR_SESSION_TRUE",
                "SINGLE_RUN_TRUE",
            ],
            "capability_commitment_preimage": (
                "FRAMED_SHA256_OF_PRIVATE_CAPABILITY_DOMAIN_UTF8_EXACTLY_32_RANDOM_PRIVATE_CAPABILITY_BYTES_AND_AB_CANONICAL_JSON_V1_BYTES_OF_THE_EXACT_CAPABILITY_COMMITMENT_BINDING_FIELDS; "
                "PRIVATE_BYTES_NEVER_SERIALIZED"
            ),
            "channel_binding_sha256_preimage": "FRAMED_SHA256_OF_CHANNEL_BINDING_DOMAIN_UTF8_AND_AB_CANONICAL_JSON_V1_EXECUTOR_SESSION_PROCESS_CHANNEL_EXPORTER_TRACK_PHASE_SUITE_RUN_NAMESPACE_AND_ASSIGNMENT_BINDINGS",
            "control_ledger_record_sha256_preimage": "FRAMED_SHA256_OF_CONTROL_LEDGER_DOMAIN_UTF8_AND_AB_CANONICAL_JSON_V1_DURABLE_SINGLE_USE_CAS_RECORD_WITH_CAPABILITY_COMMITMENT_STATE_REVISION_TRACK_PHASE_SUITE_RUN_NAMESPACE_ASSIGNMENT_AND_STOP_FENCE_BINDINGS",
            "domain_constants": {
                "authority_bundle_id": "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/authority-bundle-id",
                "authority_intersection": "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/authority-intersection",
                "authorization_request": "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/authorization-request",
                "channel_binding": "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/channel-binding",
                "control_ledger": "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/control-ledger",
                "namespace": "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/namespace",
                "private_capability": "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/private-capability",
                "run": "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/run",
                "schedule": "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/schedule",
                "scope_receipt_id": "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/scope-receipt-id",
                "scope_receipt_payload": "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/scope-receipt-payload",
                "stop_receipt_id": "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/stop-receipt-id",
            },
            "external_receipt_resolution_rule": (
                "EVERY_HASH_NAMED_RECEIPT_MUST_RESOLVE_FROM_THE_FROZEN_ALLOWLISTED_EVIDENCE_STORE_TO_DUPLICATE_FREE_CANONICAL_BYTES_WHOSE_SHA256_EQUALS_THE_REFERENCE; "
                "MISSING_NONCANONICAL_OR_HASH_MISMATCH_FAILS_CLOSED"
            ),
            "framed_sha256_kat": {
                "expected_sha256": "e280006e8a792f697155fbff2efe6b80307bdde21cb951c2cfe4bd3bd7f24f58",
                "framed_bytes_hex": "000000226167656e742d6272696467652f72756e6e65722d6672616d696e672d6b61742f7631000000000000000200ff0000000942696f436f72746578",
                "parts": ["UTF8_agent-bridge/runner-framing-kat/v1", "EMPTY_BYTES", "HEX_00ff", "UTF8_BioCortex"],
            },
            "framing_rule": (
                "FRAMED_SHA256_PREFIXES_EVERY_PART_WITH_ITS_UNSIGNED_FOUR_BYTE_BIG_ENDIAN_BYTE_LENGTH_THEN_HASHES_THE_EXACT_CONCATENATION; "
                "SHA256_FIELDS_USED_AS_BINARY_PARTS_ARE_RAW_32_BYTES_DECODED_FROM_LOWERCASE_HEX"
            ),
            "namespace_id_rule": "FRAMED_SHA256_OF_NAMESPACE_DOMAIN_AND_RAW_32_BYTE_SIMULATION_RUN_ID_USING_FOUR_BYTE_BIG_ENDIAN_LENGTH_PREFIXES",
            "receipt_id_preimage": "FRAMED_SHA256_OF_SCOPE_RECEIPT_ID_DOMAIN_UTF8_ARTIFACT_TYPE_UTF8_RAW_32_BYTE_CANONICAL_PAYLOAD_SHA256_AND_RAW_32_BYTE_SIGNATURE_RECEIPT_SHA256",
            "scope_receipt_payload_preimage": "FRAMED_SHA256_OF_SCOPE_RECEIPT_PAYLOAD_DOMAIN_UTF8_AND_AB_CANONICAL_JSON_V1_SCOPE_RECEIPT_BYTES_WITH_CANONICAL_PAYLOAD_SHA256_RECEIPT_ID_AND_SIGNATURE_RECEIPT_SHA256_OMITTED",
            "signature_receipt_sha256_preimage": "SHA256_OF_AB_CANONICAL_JSON_V1_SIGNATURE_VERIFICATION_RECEIPT_WITH_THE_REQUIRED_FIELDS_AND_NO_ADDITIONAL_FIELDS",
            "signature_rule": "RESOLVE_SIGNATURE_RECEIPT_BY_SHA256_AND_RESOLVE_SIGNATURE_SHA256_TO_THE_EXACT_NONSECRET_RAW_SIGNATURE_BYTES; RESOLVE_THE_EXACT_TRUST_POLICY_PUBLIC_KEY_VERSION_ROLE_MAPPING_AND_ALGORITHM; THE_VERIFIER_MUST_ACTIVELY_VERIFY_THE_SIGNATURE_OVER_THE_EXACT_RAW_32_BYTE_CANONICAL_PAYLOAD_SHA256_NOT_HEX_TEXT_AND_MUST_NOT_TRUST_SIGNATURE_VALID_TRUE_ALONE; THEN_VERIFY_ROLE_PRINCIPAL_AUTHORIZATION_REQUEST_REVOCATION_EPOCH_AND_VERIFICATION_TIME",
            "signature_verification_receipt_required_fields": [
                "SCHEMA",
                "ARTIFACT_TYPE",
                "ROLE",
                "AUTHORITY_PRINCIPAL_ID_SHA256",
                "AUTHORIZATION_REQUEST_SHA256",
                "CANONICAL_PAYLOAD_SHA256",
                "TRUST_POLICY_SHA256",
                "VERIFICATION_KEY_VERSION_SHA256",
                "SIGNATURE_ALGORITHM",
                "SIGNATURE_SHA256",
                "SIGNATURE_VALID_TRUE",
                "REVOCATION_EPOCH",
                "VERIFIED_AT_UTC",
            ],
            "simulation_run_id_rule": "FRAMED_SHA256_OF_RUN_DOMAIN_TRACK_ID_CASE_ID_REPETITION_INDEX_AS_FOUR_BIG_ENDIAN_BYTES_RAW_32_BYTE_CONFIGURATION_SHA256_AND_RAW_32_BYTE_ASSIGNMENT_SHA256_USING_FOUR_BYTE_BIG_ENDIAN_LENGTH_PREFIXES",
            "suite_id_rule": "SUITE_ID_EQUALS_SHA256_OF_THE_FROZEN_PREDECESSOR_OFFLINE_HARNESS_SUITE_RECEIPT_BOUND_BY_OFFLINE_HARNESS_MANIFEST_SHA256",
        },
        "E_AUTHORITY_INTEGRITY",
        "authority integrity catalog",
    )
    kat_parts = (
        b"agent-bridge/runner-framing-kat/v1",
        b"",
        bytes.fromhex("00ff"),
        b"BioCortex",
    )
    framed = _framed_bytes(*kat_parts)
    kat = contract["authority_integrity"]["framed_sha256_kat"]
    require(framed.hex() == kat["framed_bytes_hex"], "E_FRAMING_KAT", "framed bytes KAT mismatch")
    require(sha256_bytes(framed) == kat["expected_sha256"], "E_FRAMING_KAT", "framed SHA-256 KAT mismatch")


def _validate_stop_control_plane(contract: dict[str, Any]) -> None:
    require_equal(
        contract["stop_control_plane"],
        {
            "authority_rule": "INDEPENDENT_CURRENT_REDUCTIVE_ONLY_CAPABILITY_USABLE_BY_OWNER_CUSTODIAN_EMERGENCY_OPERATOR_OR_AN_ENUMERATED_AUTOMATIC_TRIGGER_EVEN_AFTER_EXECUTION_CAPABILITY_EXPIRY_REVOCATION_OR_FENCE",
            "counted_in_experiment_adapter_count": False,
            "failure_rule": "ANY_CONTROL_INTERFACE_FAILURE_ADDS_A_DURABLE_CONTROL_PLANE_FAILURE_ID_FENCES_EXECUTION_RETAINS_THE_ROW_PRESERVES_AVAILABLE_EVIDENCE_ENTERS_STOP_FAILED_QUARANTINED_AND_REQUIRES_MANUAL_ESCALATION_WITHOUT_EXPANDING_SCOPE",
            "interface_count": 5,
            "interfaces": [
                {
                    "allowed_operations": ["CAS_EXACT_RUN_CAPABILITY_TO_STOP_FENCED", "BLOCK_NEW_CALLS_FOR_EXACT_RUN"],
                    "credential_class": "STOP_CAPABILITY_FENCE_CONTROL",
                    "forbidden_operations": ["UNFENCE_OR_REAUTHORIZE_EXECUTION", "CROSS_RUN_FENCE"],
                    "interface_id": "CAPABILITY_FENCE_CONTROL",
                    "receipt_fields": ["CONTROL_LEDGER_REVISION", "CAPABILITY_COMMITMENT_SHA256", "FENCE_RECEIPT_SHA256"],
                },
                {
                    "allowed_operations": ["DISARM_EXACT_ASSIGNED_CUT", "ISOLATE_EXACT_ASSIGNED_RUN_EGRESS"],
                    "credential_class": "STOP_FAULT_DISARM_EGRESS_CONTROL",
                    "forbidden_operations": ["ARM_OR_TRIGGER_FAULT", "CROSS_NAMESPACE_CONTROL"],
                    "interface_id": "FAULT_DISARM_AND_EGRESS_ISOLATION_CONTROL",
                    "receipt_fields": ["DISARM_RECEIPT_SHA256", "EGRESS_ISOLATION_RECEIPT_SHA256"],
                },
                {
                    "allowed_operations": ["REVOKE_EXACT_RUN_CREDENTIAL_LEASES", "CONFIRM_ZERO_ACTIVE_LEASE_COMMITMENTS"],
                    "credential_class": "STOP_CREDENTIAL_REVOCATION_CONTROL",
                    "forbidden_operations": ["ISSUE_OR_RENEW_CREDENTIAL", "REVOKE_OUTSIDE_EXACT_RUN_SCOPE"],
                    "interface_id": "CREDENTIAL_BROKER_REVOCATION_CONTROL",
                    "receipt_fields": ["REVOCATION_RECEIPT_SHA256", "ACTIVE_LEASE_COMMITMENTS_AFTER_STOP"],
                },
                {
                    "allowed_operations": ["PERSIST_CURRENT_ROW_DURABLE_STATE_AND_SAFE_EVIDENCE", "CONFIRM_RETENTION_BINDINGS"],
                    "credential_class": "STOP_DURABLE_EVIDENCE_RETENTION_CONTROL",
                    "forbidden_operations": ["DELETE_OR_RECLASSIFY_RETAINED_ROW", "PERSIST_SECRET_MATERIAL"],
                    "interface_id": "DURABLE_EVIDENCE_RETENTION_CONTROL",
                    "receipt_fields": ["CURRENT_RETAINED_ROW_SHA256", "EVIDENCE_BUNDLE_SHA256", "RETENTION_RECEIPT_SHA256"],
                },
                {
                    "allowed_operations": ["FREEZE_EXACT_ASSIGNED_RESOURCES", "REDUCTIVE_TEARDOWN_WITHIN_EXACT_CLEANUP_SCOPE"],
                    "credential_class": "STOP_SCOPED_RESOURCE_CLEANUP_CONTROL",
                    "forbidden_operations": ["CREATE_OR_EXPAND_RESOURCE_SCOPE", "DELETE_EVIDENCE_AUTHORITY_OR_RETAINED_ROW"],
                    "interface_id": "SCOPED_RESOURCE_CLEANUP_CONTROL",
                    "receipt_fields": ["CLEANUP_CAPABILITY_COMMITMENT_SHA256", "CLEANUP_STATUS", "CLEANUP_COMPLETION_RECEIPT_SHA256"],
                },
            ],
            "ordering_rule": "CAPABILITY_FENCE_AND_NEW_CALL_BLOCK_FIRST_THEN_ROW_AND_DURABLE_STATE_RETENTION_THEN_FAULT_DISARM_AND_EGRESS_ISOLATION_THEN_CREDENTIAL_REVOCATION_THEN_EVIDENCE_PERSIST_CONFIRMATION_THEN_SCOPED_REDUCTIVE_CLEANUP",
            "shared_execution_credential_allowed": False,
            "stop_receipt_integrity_rule": (
                "STOP_ID_EQUALS_FRAMED_SHA256_OF_STOP_RECEIPT_ID_DOMAIN_UTF8_AND_AB_CANONICAL_JSON_V1_COMPLETE_STOP_RECEIPT_BYTES_WITH_STOP_ID_AND_SIGNATURE_RECEIPT_SHA256_OMITTED; "
                "SIGNATURE_RECEIPT_AND_RAW_SIGNATURE_BYTES_MUST_RESOLVE_AND_BE_ACTIVELY_VERIFIED_OVER_THE_EXACT_RAW_32_BYTE_STOP_ID_NOT_HEX_TEXT_WITH_EXACT_BINDINGS_TRIGGER_REASON_ROLE_REVOCATION_EPOCH_TIMESTAMPS_COMPONENT_RECEIPTS_AND_LIFECYCLE_STATE"
            ),
            "timestamp_rule": (
                "ALL_TIMESTAMPS_ARE_STRICT_RFC3339_UTC_SECONDS_CALENDAR_VALID; STOP_REQUESTED_AT_IS_TRUSTED_UTC; "
                "NONNULL_CLEANUP_COMPLETED_AT_AND_STOP_COMPLETED_AT_ARE_NOT_EARLIER_THAN_STOP_REQUESTED_AT; "
                "STOP_COMPLETED_AT_IS_NOT_EARLIER_THAN_CLEANUP_COMPLETED_AT"
            ),
        },
        "E_STOP_CONTROL_PLANE",
        "stop control plane",
    )


def validate_adapter_contract(contract: dict[str, Any], *, bind_hash: bool = True) -> None:
    _validate_contract_identity(contract)
    _validate_authority_model(contract)
    _validate_start_stop(contract)
    _validate_adapters(contract)
    _validate_routing(contract)
    _validate_acceptance_evidence_retention(contract)
    _validate_credentials_recovery_boundary(contract)
    _validate_predecessor_lineage(contract)
    _validate_authority_integrity(contract)
    _validate_stop_control_plane(contract)
    require_equal(
        contract["non_claims"],
        [
            "NO_PROVIDER_EXPERIMENT_EXECUTED",
            "NO_CREDENTIAL_RESOURCE_COST_OR_ENDPOINT_AUTHORITY_BOUND",
            "NO_EXACTLY_ONCE_PROVIDER_RPC_OR_SIGNATURE_CREATION",
            "NO_PROVIDER_PROCESSING_INFERENCE_FROM_CLIENT_OR_PROXY_EVIDENCE",
            "NO_PRODUCTION_READINESS_OUTPUT_PERMIT_OR_CONDITION_OUTPUT_AUTHORIZATION",
            "NO_CROSS_TRACK_CERTIFICATION_RANKING_OR_SUBSTITUTION",
            "NO_REVISION_BUMP_WATCH_TIMEOUT_EOF_OR_SEAL_CONTINUITY_PROOF",
        ],
        "E_NON_CLAIMS",
        "non-claims",
    )
    require(type(contract["official_source_claims"]) is list and len(contract["official_source_claims"]) == 10, "E_OFFICIAL_SOURCES", "official source catalog mismatch")
    claim_ids = [claim.get("claim_id") for claim in contract["official_source_claims"]]
    require(
        claim_ids
        == [
            "GID_RUNNER_01",
            "GSP_RUNNER_01",
            "GKM_RUNNER_01",
            "GKM_RUNNER_02",
            "ETC_RUNNER_01",
            "ETC_RUNNER_02",
            "ETC_RUNNER_03",
            "OBA_RUNNER_01",
            "OBA_RUNNER_02",
            "OBA_RUNNER_03",
        ],
        "E_OFFICIAL_SOURCES",
        "official source ids drift",
    )
    expected_urls = [
        "https://docs.cloud.google.com/iam/docs/best-practices-for-using-workload-identity-federation?hl=en",
        "https://docs.cloud.google.com/spanner/docs/transactions",
        "https://docs.cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/asymmetricSign",
        "https://docs.cloud.google.com/kms/docs/audit-logging",
        "https://etcd.io/docs/v3.6/learning/api_guarantees/",
        "https://etcd.io/docs/v3.6/op-guide/recovery/",
        "https://etcd.io/docs/v3.6/op-guide/security/",
        "https://openbao.org/api-docs/secret/transit/",
        "https://openbao.org/docs/internals/high-availability/",
        "https://openbao.org/docs/next/audit/",
    ]
    for claim, expected_url in zip(contract["official_source_claims"], expected_urls):
        exact_keys(claim, ("claim", "claim_id", "evidence_class", "retrieved_on", "url"), "E_OFFICIAL_SOURCES", "official source claim")
        require(claim["evidence_class"] == "OFFICIAL_DOCUMENTATION_DIRECT", "E_OFFICIAL_SOURCES", "official evidence class drift")
        require(claim["retrieved_on"] == "2026-07-15", "E_OFFICIAL_SOURCES", "official source currentness drift")
        require(claim["url"] == expected_url, "E_OFFICIAL_SOURCES", "official source URL drift")
    profile = contract["profile_contract"]
    exact_keys(profile, ("managed_required_fields", "self_hosted_required_fields", "source_currentness_rule"), "E_PROFILE_FIELDS", "profile contract")
    require_equal(
        profile["managed_required_fields"],
        [
            "PROJECT_INSTANCE_DATABASE_DIALECT_REGION_IDENTITY_SHA256",
            "WORKLOAD_IDENTITY_OR_EQUIVALENT_SHORT_LIVED_CREDENTIAL_BROKER_PROFILE_SHA256",
            "SPANNER_CLIENT_BUILD_API_DESCRIPTOR_RETRY_TIMEOUT_AND_ISOLATION_PROFILE_SHA256",
            "EXACT_CRYPTOKEYVERSION_ALGORITHM_STATE_PROTECTION_PUBLIC_KEY_AND_METADATA_SHA256",
            "KMS_TRANSPORT_RETRY_DISABLED_AND_WIRE_OBSERVATION_PROFILE_SHA256",
            "FAULT_PROXY_BUILD_CONFIGURATION_TOPOLOGY_AND_TRUST_PIN_SHA256",
            "RESOURCE_PRINCIPAL_QUOTA_COST_AND_RETENTION_SCOPE_SHA256",
            "STOP_CONTROL_PLANE_BROKER_EGRESS_EVIDENCE_CLEANUP_AND_MANIFEST_SHA256",
            "OFFICIAL_SOURCE_SNAPSHOT_AND_CURRENTNESS_SHA256",
        ],
        "E_PROFILE_MANAGED",
        "managed profile fields",
    )
    require_equal(
        profile["self_hosted_required_fields"],
        [
            "ETCD_OPENBAO_BINARY_OR_IMAGE_CLIENT_AND_CONFIGURATION_SHA256",
            "MEMBER_NODE_CLUSTER_INCARNATION_TOPOLOGY_QUORUM_TLS_AND_RESOURCE_CAP_SHA256",
            "ETCD_CLIENT_PEER_MTLS_RBAC_AND_IDENTITY_ENFORCEMENT_SHA256",
            "SNAPSHOT_REVISION_RESTORE_BUMP_MARK_COMPACTED_AND_NEW_IDENTITY_SHA256",
            "TRANSIT_MOUNT_KEY_VERSION_PUBLIC_KEY_MINIMUM_VERSION_AND_REQUEST_MODE_SHA256",
            "HA_ROUTE_REDIRECT_FORWARD_AUDIT_AND_REQUEST_CORRELATION_SHA256",
            "OPENBAO_AUDIT_DEVICE_UNION_HEALTH_AND_NONAUDITED_PATH_ACCOUNTING_SHA256",
            "FAULT_CONTROLLER_BUILD_TOPOLOGY_SEED_AND_MONOTONIC_CLOCK_SHA256",
            "EXTERNAL_WITNESS_IDENTITY_CAS_AND_INDEPENDENT_FAILURE_DOMAIN_SHA256",
            "STOP_CONTROL_PLANE_BROKER_EGRESS_EVIDENCE_CLEANUP_AND_MANIFEST_SHA256",
            "RESOURCE_PRINCIPAL_COST_RETENTION_AND_OFFICIAL_SOURCE_CURRENTNESS_SHA256",
        ],
        "E_PROFILE_SELF_HOSTED",
        "self-hosted profile fields",
    )
    require(profile["source_currentness_rule"] == "REFETCH_AND_FREEZE_OFFICIAL_PAGE_OR_UPSTREAM_DESCRIPTOR_HASHES_BEFORE_PREFLIGHT_AND_EXECUTION", "E_PROFILE_CURRENTNESS", "profile currentness rule drift")
    if bind_hash:
        require(sha256_value(contract) == EXPECTED_CONTRACT_SHA256, "E_CONTRACT_HASH", "adapter contract hash drift")


AUTHORITY_SLOT_TYPES = {
    "owner_scope_receipt": "OWNER_SCOPE_RECEIPT",
    "custodian_credential_receipt": "CUSTODIAN_CREDENTIAL_RECEIPT",
    "resource_authority_receipt": "RESOURCE_AUTHORITY_RECEIPT",
    "cost_authority_receipt": "COST_AUTHORITY_RECEIPT",
    "emergency_stop_authority_receipt": "EMERGENCY_STOP_AUTHORITY_RECEIPT",
}


def validate_authority_schema_semantics(schema: dict[str, Any], *, bind_hash: bool = True) -> None:
    validate_schema_document(schema, AUTHORITY_RECEIPT_SCHEMA, "authority bundle schema")
    require(set(schema["required"]) == set(schema["properties"]), "E_AUTHORITY_SCHEMA_ROOT", "authority root is not fully required")
    expected_root_fields = {
        "adapter_build_sha256", "adapter_set_manifest_sha256", "assignment_sha256",
        "authority_intersection", "bundle_id", "case_id", "cleanup_policy_sha256",
        "condition_output_authorized", "configuration_sha256", "contract_sha256",
        "cost_authority_receipt", "cost_scope_sha256", "credential_scope_sha256",
        "currentness", "custodian_credential_receipt", "effective_allowed_operations",
        "emergency_stop_authority_receipt", "execution_capability_commitment",
        "field_level_intersection_sha256", "namespace_id", "offline_harness_manifest_sha256",
        "owner_scope_receipt", "phase", "profile_sha256", "public_bundle_is_bearer_capability",
        "receipt_is_output_permit", "repetition_index", "resource_authority_receipt",
        "resource_scope_sha256", "retention_policy_sha256", "revocation_epoch",
        "runner_build_sha256", "schedule_sha256", "schema", "simulation_run_id",
        "stop_control_plane_manifest_sha256", "suite_id", "track_id",
    }
    require(set(schema["properties"]) == expected_root_fields, "E_AUTHORITY_SCHEMA_ROOT", "authority root catalog drift")
    require_equal(schema["properties"]["repetition_index"], {"maximum": 30, "minimum": 1, "type": "integer"}, "E_AUTHORITY_REPETITION_SCHEMA", "authority repetition range")
    expected_defs = {
        "authority_intersection",
        "caps",
        "case_id",
        "cost_authority_receipt",
        "currentness",
        "custodian_credential_receipt",
        "emergency_stop_authority_receipt",
        "execution_capability_commitment",
        "owner_scope_receipt",
        "resource_authority_receipt",
        "scope_receipt",
        "sha256",
        "track_id",
        "utc",
    }
    require(set(schema["$defs"]) == expected_defs, "E_AUTHORITY_SCHEMA_DEFS", "authority defs catalog drift")
    scope = schema["$defs"]["scope_receipt"]
    require(scope["type"] == "object" and scope["additionalProperties"] is False, "E_AUTHORITY_SCOPE_SCHEMA", "scope receipt not closed")
    require(set(scope["required"]) == set(scope["properties"]), "E_AUTHORITY_SCOPE_SCHEMA", "scope receipt fields not fully required")
    require_equal(scope["properties"]["artifact_type"]["enum"], EXPECTED_AUTHORITY_ARTIFACTS, "E_AUTHORITY_ARTIFACT_ENUM", "authority artifact enum")
    require_equal(scope["properties"]["allowed_repetition_indices"], {"items": {"maximum": 30, "minimum": 1, "type": "integer"}, "minItems": 1, "type": "array", "uniqueItems": True}, "E_AUTHORITY_REPETITION_SCHEMA", "receipt repetition range")
    for slot, artifact_type in AUTHORITY_SLOT_TYPES.items():
        reference = schema["properties"][slot]
        require_equal(reference, {"$ref": f"#/$defs/{slot}"}, "E_AUTHORITY_SLOT_REF", f"{slot} ref")
        role_schema = schema["$defs"][slot]
        require(type(role_schema.get("allOf")) is list and len(role_schema["allOf"]) == 2, "E_AUTHORITY_SLOT_SCHEMA", f"{slot} allOf shape")
        require_equal(role_schema["allOf"][0], {"$ref": "#/$defs/scope_receipt"}, "E_AUTHORITY_SLOT_SCHEMA", f"{slot} base ref")
        require_equal(
            role_schema["allOf"][1],
            {"properties": {"artifact_type": {"const": artifact_type}}, "required": ["artifact_type"]},
            "E_AUTHORITY_SLOT_SCHEMA",
            f"{slot} role narrowing",
        )
    cap = schema["$defs"]["execution_capability_commitment"]
    require(set(cap["required"]) == set(cap["properties"]), "E_AUTHORITY_CAP_SCHEMA", "capability fields not fully required")
    for key, expected in {
        "private_capability_bytes_serialized": False,
        "single_consume": True,
        "single_executor_session": True,
        "single_run": True,
    }.items():
        require(cap["properties"][key].get("const") is expected, "E_AUTHORITY_CAP_SCHEMA", f"capability {key} fence drift")
    intersection = schema["$defs"]["authority_intersection"]
    require(set(intersection["required"]) == set(intersection["properties"]), "E_AUTHORITY_INTERSECTION_SCHEMA", "intersection fields not fully required")
    require(intersection["properties"]["nonempty_exact_intersection"].get("const") is True, "E_AUTHORITY_INTERSECTION_SCHEMA", "nonempty exact-intersection fence missing")
    root_consts = {
        "condition_output_authorized": False,
        "public_bundle_is_bearer_capability": False,
        "receipt_is_output_permit": False,
    }
    for key, expected in root_consts.items():
        require(schema["properties"][key].get("const") is expected, "E_AUTHORITY_PUBLIC_FENCE", f"authority root {key} drift")
    if bind_hash:
        require(sha256_value(schema) == EXPECTED_AUTHORITY_SCHEMA_SHA256, "E_AUTHORITY_SCHEMA_HASH", "authority schema hash drift")


def validate_stop_schema_semantics(schema: dict[str, Any], *, bind_hash: bool = True) -> None:
    validate_schema_document(schema, STOP_RECEIPT_SCHEMA, "stop receipt schema")
    require(set(schema["required"]) == set(schema["properties"]), "E_STOP_SCHEMA_ROOT", "stop root is not fully required")
    expected_root_fields = {
        "adapter_build_sha256", "adapter_set_manifest_sha256", "application_calls",
        "assignment_sha256", "authority_bundle_sha256", "authority_phase",
        "authority_revocation_epoch", "automatic_rerun_allowed", "capability_fence_receipt_sha256",
        "capability_invalidated", "case_id", "cleanup", "cleanup_policy_sha256",
        "configuration_sha256", "continuation_allowed", "contract_sha256",
        "control_plane_failure_ids", "cost", "cost_scope_sha256", "credential",
        "credential_scope_sha256", "current_retained_row_sha256", "durable_state",
        "evidence_bundle_sha256", "evidence_preserved", "fault",
        "field_level_intersection_sha256", "last_completed_row_sha256",
        "manual_escalation_required", "namespace_id", "new_calls_blocked",
        "offline_harness_manifest_sha256", "profile_sha256", "receipt_is_execution_authority",
        "receipt_is_output_permit", "repetition_index", "resource_scope_sha256",
        "retained_row_preserved", "retention_policy_sha256", "retention_receipt_sha256",
        "runner_build_sha256", "schedule_sha256", "schema", "signature_receipt_sha256",
        "simulation_run_id", "stop_completed_at_utc", "stop_control_plane_manifest_sha256",
        "stop_id", "stop_lifecycle_state", "stop_reason", "stop_requested_at_utc",
        "stop_trigger", "stop_trigger_role", "suite_id", "track_id",
        "unresolved_ambiguity_ids", "wire_attempts",
    }
    require(set(schema["properties"]) == expected_root_fields, "E_STOP_SCHEMA_ROOT", "stop root catalog drift")
    require_equal(schema["properties"]["repetition_index"], {"maximum": 30, "minimum": 1, "type": "integer"}, "E_STOP_REPETITION_SCHEMA", "stop repetition range")
    require(set(schema["$defs"]) == {"cleanup", "cost", "credential_stop", "durable_state", "fault_stop", "sha256", "utc"}, "E_STOP_SCHEMA_DEFS", "stop defs catalog drift")
    for name in ("cleanup", "cost", "credential_stop", "durable_state", "fault_stop"):
        definition = schema["$defs"][name]
        require(definition.get("type") == "object" and definition.get("additionalProperties") is False, "E_STOP_SCHEMA_CLOSURE", f"{name} is not closed")
        require(set(definition["required"]) == set(definition["properties"]), "E_STOP_SCHEMA_CLOSURE", f"{name} fields not fully required")
    for key in ("automatic_rerun_allowed", "continuation_allowed", "receipt_is_execution_authority", "receipt_is_output_permit"):
        require(schema["properties"][key].get("const") is False, "E_STOP_ABSORPTION_SCHEMA", f"stop {key} must be false")
    for key in ("capability_invalidated", "evidence_preserved", "new_calls_blocked", "retained_row_preserved"):
        require(schema["properties"][key].get("const") is True, "E_STOP_ABSORPTION_SCHEMA", f"stop {key} must be true")
    require_equal(
        schema["properties"]["stop_trigger_role"]["enum"],
        ["OWNER", "CUSTODIAN", "EMERGENCY_OPERATOR", "SYSTEM_BOUNDARY", "SYSTEM_EXPIRY_OR_REVOCATION"],
        "E_STOP_ROLE_SCHEMA",
        "stop trigger roles",
    )
    require("STOPPED" not in schema["properties"]["stop_reason"].get("enum", []), "E_STOP_REASON_SCHEMA", "state leaked into stop reasons")
    require(type(schema.get("allOf")) is list and len(schema["allOf"]) >= 20, "E_STOP_CROSS_FIELD_SCHEMA", "stop cross-field guards missing")
    if bind_hash:
        require(sha256_value(schema) == EXPECTED_STOP_SCHEMA_SHA256, "E_STOP_SCHEMA_HASH", "stop schema hash drift")


def _kat_hash(label: str) -> str:
    return sha256_bytes(label.encode("utf-8"))


def _framed_bytes(*parts: bytes) -> bytes:
    result = bytearray()
    for part in parts:
        require(len(part) <= 0xFFFFFFFF, "E_FRAMING_LENGTH", "framed part is too long")
        result.extend(len(part).to_bytes(4, "big"))
        result.extend(part)
    return bytes(result)


def _framed_sha256(*parts: bytes) -> str:
    return sha256_bytes(_framed_bytes(*parts))


def _domain_canonical_hash(domain: str, value: Any) -> str:
    return _framed_sha256(domain.encode("utf-8"), canonical_bytes(value))


def _legacy_kat_scope_receipt(artifact_type: str) -> dict[str, Any]:
    result = {
        "adapter_build_sha256": _kat_hash("adapter-build"),
        "adapter_set_manifest_sha256": _kat_hash("adapter-set"),
        "allowed_case_ids": ["M00"],
        "allowed_operations": ["RUN_EXACT_ASSIGNED_OPERATION"],
        "allowed_repetition_indices": [1],
        "artifact_type": artifact_type,
        "assignment_sha256": _kat_hash("assignment"),
        "authority_principal_id_sha256": _kat_hash(f"principal-{artifact_type}"),
        "authorization_request_sha256": _kat_hash(f"request-{artifact_type}"),
        "canonical_payload_sha256": _kat_hash(f"payload-{artifact_type}"),
        "cleanup_policy_sha256": _kat_hash("cleanup"),
        "configuration_sha256": EXPECTED_LINEAGE["offline_configuration_sha256"],
        "contract_sha256": EXPECTED_CONTRACT_SHA256,
        "cost_scope_sha256": _kat_hash("cost-scope"),
        "credential_scope_sha256": _kat_hash("credential-scope"),
        "expires_at_utc": "2026-07-15T21:00:00Z",
        "forbidden_operations": ["ANY_UNASSIGNED_OPERATION"],
        "issued_at_utc": "2026-07-15T20:00:00Z",
        "nonce_sha256": _kat_hash(f"nonce-{artifact_type}"),
        "not_before_utc": "2026-07-15T19:59:00Z",
        "offline_harness_manifest_sha256": EXPECTED_LINEAGE["offline_harness_manifest_sha256"],
        "phase": "EXPERIMENT_EXECUTION_GRANT",
        "profile_sha256": _kat_hash("profile"),
        "receipt_id": _kat_hash(f"receipt-{artifact_type}"),
        "receipt_is_output_permit": False,
        "resource_scope_sha256": _kat_hash("resource-scope"),
        "retention_policy_sha256": _kat_hash("retention"),
        "revocation_epoch": 7,
        "runner_build_sha256": _kat_hash("runner-build"),
        "simulation_run_id": _kat_hash("run-id"),
        "namespace_id": _kat_hash("namespace"),
        "schedule_sha256": EXPECTED_LINEAGE["offline_schedule_sha256"],
        "signature_receipt_sha256": _kat_hash(f"signature-{artifact_type}"),
        "stop_control_plane_manifest_sha256": _kat_hash("stop-control-plane"),
        "suite_id": _kat_hash("suite"),
        "track_id": MANAGED_TRACK,
        "trust_policy_sha256": _kat_hash("trust-policy"),
    }
    if artifact_type == "EMERGENCY_STOP_AUTHORITY_RECEIPT":
        result["allowed_operations"] = [
            "BLOCK_NEW_CALLS_FOR_EXACT_RUN",
            "CAS_EXACT_RUN_CAPABILITY_TO_STOP_FENCED",
            "CONFIRM_RETENTION_BINDINGS",
            "DISARM_EXACT_ASSIGNED_CUT",
            "ISOLATE_EXACT_ASSIGNED_RUN_EGRESS",
            "PERSIST_CURRENT_ROW_DURABLE_STATE_AND_SAFE_EVIDENCE",
            "REDUCTIVE_TEARDOWN_WITHIN_EXACT_CLEANUP_SCOPE",
            "REVOKE_EXACT_RUN_CREDENTIAL_LEASES",
        ]
        result["forbidden_operations"] = [
            "ARM_OR_TRIGGER_FAULT",
            "AUTHORIZE_CONDITION_OUTPUT_OR_OUTPUT_PERMIT",
            "CREATE_OR_EXPAND_RESOURCE_SCOPE",
            "SIGN_PROVIDER_MESSAGE",
            "START_OR_RESUME_EXPERIMENT",
        ]
    return result


def _legacy_authority_kat_instance() -> dict[str, Any]:
    receipts = {
        slot: _kat_scope_receipt(artifact_type)
        for slot, artifact_type in AUTHORITY_SLOT_TYPES.items()
    }
    intersection_without_hash = {
        "adapter_build_sha256": _kat_hash("adapter-build"),
        "adapter_set_manifest_sha256": _kat_hash("adapter-set"),
        "assignment_sha256": _kat_hash("assignment"),
        "cleanup_policy_sha256": _kat_hash("cleanup"),
        "configuration_sha256": EXPECTED_LINEAGE["offline_configuration_sha256"],
        "contract_sha256": EXPECTED_CONTRACT_SHA256,
        "cost_scope_sha256": _kat_hash("cost-scope"),
        "credential_scope_sha256": _kat_hash("credential-scope"),
        "effective_allowed_case_ids": ["M00"],
        "effective_allowed_operations": ["RUN_EXACT_ASSIGNED_OPERATION"],
        "effective_allowed_repetition_indices": [1],
        "nonempty_exact_intersection": True,
        "offline_harness_manifest_sha256": EXPECTED_LINEAGE["offline_harness_manifest_sha256"],
        "phase": "EXPERIMENT_EXECUTION_GRANT",
        "profile_sha256": _kat_hash("profile"),
        "resource_scope_sha256": _kat_hash("resource-scope"),
        "retention_policy_sha256": _kat_hash("retention"),
        "simulation_run_id": _kat_hash("run-id"),
        "namespace_id": _kat_hash("namespace"),
        "runner_build_sha256": _kat_hash("runner-build"),
        "schedule_sha256": EXPECTED_LINEAGE["offline_schedule_sha256"],
        "stop_control_plane_manifest_sha256": _kat_hash("stop-control-plane"),
        "suite_id": _kat_hash("suite"),
        "track_id": MANAGED_TRACK,
    }
    intersection = dict(intersection_without_hash)
    intersection["field_level_intersection_sha256"] = _domain_canonical_hash(
        "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/authority-intersection",
        intersection_without_hash,
    )
    capability = {
        "adapter_build_sha256": _kat_hash("adapter-build"),
        "adapter_set_manifest_sha256": _kat_hash("adapter-set"),
        "assignment_sha256": _kat_hash("assignment"),
        "capability_commitment_sha256": _kat_hash("capability"),
        "channel_binding_sha256": _kat_hash("channel"),
        "control_ledger_record_sha256": _kat_hash("ledger"),
        "configuration_sha256": EXPECTED_LINEAGE["offline_configuration_sha256"],
        "contract_sha256": EXPECTED_CONTRACT_SHA256,
        "offline_harness_manifest_sha256": EXPECTED_LINEAGE["offline_harness_manifest_sha256"],
        "phase": "EXPERIMENT_EXECUTION_GRANT",
        "private_capability_bytes_serialized": False,
        "profile_sha256": _kat_hash("profile"),
        "simulation_run_id": _kat_hash("run-id"),
        "namespace_id": _kat_hash("namespace"),
        "case_id": "M00",
        "repetition_index": 1,
        "runner_build_sha256": _kat_hash("runner-build"),
        "schedule_sha256": EXPECTED_LINEAGE["offline_schedule_sha256"],
        "single_consume": True,
        "single_executor_session": True,
        "single_run": True,
        "state": "UNUSED",
        "stop_control_plane_manifest_sha256": _kat_hash("stop-control-plane"),
        "suite_id": _kat_hash("suite"),
        "track_id": MANAGED_TRACK,
    }
    bundle = {
        "adapter_build_sha256": _kat_hash("adapter-build"),
        "adapter_set_manifest_sha256": _kat_hash("adapter-set"),
        "assignment_sha256": _kat_hash("assignment"),
        "authority_intersection": intersection,
        "bundle_id": "0" * 64,
        "case_id": "M00",
        "condition_output_authorized": False,
        "configuration_sha256": EXPECTED_LINEAGE["offline_configuration_sha256"],
        "contract_sha256": EXPECTED_CONTRACT_SHA256,
        "cost_authority_receipt": receipts["cost_authority_receipt"],
        "currentness": {
            "checked_at_utc": "2026-07-15T20:01:00Z",
            "cost_budget_reserved": True,
            "credential_lease_current": True,
            "profile_current": True,
            "resource_budget_reserved": True,
            "revocation_epoch": 7,
            "row_currentness_receipt_sha256": _kat_hash("row-currentness"),
            "trusted_time_receipt_sha256": _kat_hash("trusted-time"),
        },
        "custodian_credential_receipt": receipts["custodian_credential_receipt"],
        "emergency_stop_authority_receipt": receipts["emergency_stop_authority_receipt"],
        "execution_capability_commitment": capability,
        "namespace_id": _kat_hash("namespace"),
        "offline_harness_manifest_sha256": EXPECTED_LINEAGE["offline_harness_manifest_sha256"],
        "owner_scope_receipt": receipts["owner_scope_receipt"],
        "phase": "EXPERIMENT_EXECUTION_GRANT",
        "profile_sha256": _kat_hash("profile"),
        "public_bundle_is_bearer_capability": False,
        "receipt_is_output_permit": False,
        "resource_authority_receipt": receipts["resource_authority_receipt"],
        "repetition_index": 1,
        "runner_build_sha256": _kat_hash("runner-build"),
        "schedule_sha256": EXPECTED_LINEAGE["offline_schedule_sha256"],
        "schema": AUTHORITY_RECEIPT_SCHEMA,
        "simulation_run_id": _kat_hash("run-id"),
        "stop_control_plane_manifest_sha256": _kat_hash("stop-control-plane"),
        "suite_id": _kat_hash("suite"),
        "track_id": MANAGED_TRACK,
    }
    bundle_preimage = {key: copy.deepcopy(value) for key, value in bundle.items() if key != "bundle_id"}
    bundle["bundle_id"] = _domain_canonical_hash(
        "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/authority-bundle-id",
        bundle_preimage,
    )
    return bundle


def _legacy_validate_authority_bundle_instance(bundle: dict[str, Any], schema: dict[str, Any]) -> None:
    validate_json_schema(bundle, schema)
    bundle_preimage = {key: copy.deepcopy(value) for key, value in bundle.items() if key != "bundle_id"}
    require(
        bundle["bundle_id"]
        == _domain_canonical_hash(
            "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/authority-bundle-id",
            bundle_preimage,
        ),
        "E_AUTHORITY_BUNDLE_ID",
        "authority bundle id preimage mismatch",
    )
    receipts = [bundle[slot] for slot in AUTHORITY_SLOT_TYPES]
    for slot, expected_type in AUTHORITY_SLOT_TYPES.items():
        require(bundle[slot]["artifact_type"] == expected_type, "E_AUTHORITY_ROLE", f"{slot} type mismatch")
    common_bindings = (
        "adapter_build_sha256",
        "adapter_set_manifest_sha256",
        "assignment_sha256",
        "cleanup_policy_sha256",
        "configuration_sha256",
        "contract_sha256",
        "cost_scope_sha256",
        "credential_scope_sha256",
        "offline_harness_manifest_sha256",
        "phase",
        "profile_sha256",
        "resource_scope_sha256",
        "retention_policy_sha256",
        "simulation_run_id",
        "namespace_id",
        "runner_build_sha256",
        "schedule_sha256",
        "stop_control_plane_manifest_sha256",
        "suite_id",
        "track_id",
    )
    intersection = bundle["authority_intersection"]
    for field in common_bindings:
        values = [receipt[field] for receipt in receipts]
        require(all(_json_equal(value, values[0]) for value in values[1:]), "E_AUTHORITY_BINDING", f"receipt {field} mismatch")
        require_equal(intersection[field], values[0], "E_AUTHORITY_INTERSECTION", f"intersection {field}")
    root_bindings = {
        "adapter_build_sha256": "adapter_build_sha256",
        "adapter_set_manifest_sha256": "adapter_set_manifest_sha256",
        "assignment_sha256": "assignment_sha256",
        "configuration_sha256": "configuration_sha256",
        "contract_sha256": "contract_sha256",
        "namespace_id": "namespace_id",
        "offline_harness_manifest_sha256": "offline_harness_manifest_sha256",
        "profile_sha256": "profile_sha256",
        "runner_build_sha256": "runner_build_sha256",
        "schedule_sha256": "schedule_sha256",
        "simulation_run_id": "simulation_run_id",
        "stop_control_plane_manifest_sha256": "stop_control_plane_manifest_sha256",
        "suite_id": "suite_id",
        "track_id": "track_id",
        "phase": "phase",
    }
    for root_field, receipt_field in root_bindings.items():
        require_equal(bundle[root_field], receipts[0][receipt_field], "E_AUTHORITY_ROOT_BINDING", root_field)
    capability = bundle["execution_capability_commitment"]
    for field in (
        "adapter_build_sha256",
        "adapter_set_manifest_sha256",
        "assignment_sha256",
        "configuration_sha256",
        "contract_sha256",
        "offline_harness_manifest_sha256",
        "phase",
        "profile_sha256",
        "simulation_run_id",
        "namespace_id",
        "runner_build_sha256",
        "schedule_sha256",
        "stop_control_plane_manifest_sha256",
        "suite_id",
        "track_id",
    ):
        require_equal(capability[field], receipts[0][field], "E_AUTHORITY_CAP_BINDING", f"capability {field}")
    require(capability["case_id"] == bundle["case_id"] and capability["repetition_index"] == bundle["repetition_index"], "E_AUTHORITY_CAP_BINDING", "capability assignment mismatch")
    require(capability["private_capability_bytes_serialized"] is False, "E_AUTHORITY_CAPABILITY", "private capability serialized")
    require(capability["single_consume"] is True and capability["single_executor_session"] is True and capability["single_run"] is True, "E_AUTHORITY_CAPABILITY", "capability is reusable")
    require(capability["state"] == "UNUSED", "E_AUTHORITY_CAPABILITY", "new authority bundle capability not unused")
    for receipt in receipts:
        require(receipt["not_before_utc"] <= receipt["issued_at_utc"] < receipt["expires_at_utc"], "E_AUTHORITY_TIME", "receipt time order invalid")
        require(receipt["not_before_utc"] <= bundle["currentness"]["checked_at_utc"] < receipt["expires_at_utc"], "E_AUTHORITY_CURRENTNESS", "currentness outside receipt window")
        require(receipt["revocation_epoch"] == bundle["currentness"]["revocation_epoch"], "E_AUTHORITY_REVOCATION", "revocation epoch mismatch")
        require(set(receipt["allowed_operations"]).isdisjoint(receipt["forbidden_operations"]), "E_AUTHORITY_OPERATION_SCOPE", "allowed/forbidden operations overlap")
        prefix = "M" if receipt["track_id"] == MANAGED_TRACK else "S"
        require(all(case_id.startswith(prefix) for case_id in receipt["allowed_case_ids"]), "E_AUTHORITY_CASE_TRACK", "case scope crosses track")
    for source_field, effective_field in (
        ("allowed_case_ids", "effective_allowed_case_ids"),
        ("allowed_operations", "effective_allowed_operations"),
        ("allowed_repetition_indices", "effective_allowed_repetition_indices"),
    ):
        participating = receipts[:4] if source_field == "allowed_operations" else receipts
        common = set(participating[0][source_field])
        for receipt in participating[1:]:
            common &= set(receipt[source_field])
        if source_field == "allowed_operations":
            forbidden_union: set[Any] = set()
            for receipt in receipts:
                forbidden_union.update(receipt["forbidden_operations"])
            common -= forbidden_union
        require(common and set(intersection[effective_field]) == common and len(intersection[effective_field]) == len(common), "E_AUTHORITY_EXACT_INTERSECTION", f"{effective_field} is not exact intersection")
    emergency = bundle["emergency_stop_authority_receipt"]
    require(set(emergency["allowed_operations"]) == set(contract_operation for contract_operation in [
        "BLOCK_NEW_CALLS_FOR_EXACT_RUN",
        "CAS_EXACT_RUN_CAPABILITY_TO_STOP_FENCED",
        "CONFIRM_RETENTION_BINDINGS",
        "DISARM_EXACT_ASSIGNED_CUT",
        "ISOLATE_EXACT_ASSIGNED_RUN_EGRESS",
        "PERSIST_CURRENT_ROW_DURABLE_STATE_AND_SAFE_EVIDENCE",
        "REDUCTIVE_TEARDOWN_WITHIN_EXACT_CLEANUP_SCOPE",
        "REVOKE_EXACT_RUN_CREDENTIAL_LEASES",
    ]), "E_EMERGENCY_SCOPE", "emergency stop receipt scope drift")
    require(set(intersection["effective_allowed_operations"]).isdisjoint(emergency["allowed_operations"]), "E_EMERGENCY_SCOPE", "emergency stop operations added positive authority")
    if bundle["phase"] == "EXPERIMENT_EXECUTION_GRANT":
        require(len(intersection["effective_allowed_case_ids"]) == 1 and len(intersection["effective_allowed_repetition_indices"]) == 1, "E_AUTHORITY_ASSIGNMENT", "execution grant is not singleton assignment")
        require(intersection["effective_allowed_case_ids"] == [bundle["case_id"]] and intersection["effective_allowed_repetition_indices"] == [bundle["repetition_index"]], "E_AUTHORITY_ASSIGNMENT", "effective assignment does not match root")
    else:
        require(all("SIGN" not in operation and "MUTATE" not in operation and "FAULT" not in operation for operation in intersection["effective_allowed_operations"]), "E_AUTHORITY_PREFLIGHT", "preflight includes active operation")
    payload = {key: copy.deepcopy(value) for key, value in intersection.items() if key != "field_level_intersection_sha256"}
    require(
        intersection["field_level_intersection_sha256"]
        == _domain_canonical_hash(
            "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/authority-intersection",
            payload,
        ),
        "E_AUTHORITY_INTERSECTION_HASH",
        "intersection hash mismatch",
    )
    require(intersection["contract_sha256"] == EXPECTED_CONTRACT_SHA256, "E_AUTHORITY_CONTRACT_BINDING", "authority contract hash mismatch")
    require(intersection["offline_harness_manifest_sha256"] == EXPECTED_LINEAGE["offline_harness_manifest_sha256"], "E_AUTHORITY_MANIFEST_BINDING", "authority predecessor manifest mismatch")
    require(intersection["schedule_sha256"] == EXPECTED_LINEAGE["offline_schedule_sha256"], "E_AUTHORITY_SCHEDULE_BINDING", "authority schedule mismatch")
    valid_cases = (
        {f"M{index:02d}" for index in range(16)}
        if bundle["track_id"] == MANAGED_TRACK
        else {f"S{index:02d}" for index in range(18)}
    )
    require(bundle["case_id"] in valid_cases, "E_AUTHORITY_CASE_TRACK", "root case is not valid for track")


SCHEDULE_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/schedule"
)
RUN_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/run"
)
NAMESPACE_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/namespace"
)
AUTHORITY_BUNDLE_ID_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/authority-bundle-id"
)
AUTHORITY_INTERSECTION_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/authority-intersection"
)
PRIVATE_CAPABILITY_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/private-capability"
)
SCOPE_RECEIPT_ID_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/scope-receipt-id"
)
SCOPE_RECEIPT_PAYLOAD_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/scope-receipt-payload"
)
STOP_RECEIPT_ID_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/stop-receipt-id"
)
PREFLIGHT_OPERATIONS = {
    "READ_COST_BUDGET_METADATA",
    "READ_CREDENTIAL_LEASE_METADATA",
    "READ_EVIDENCE_SINK_HEALTH",
    "READ_PROVIDER_PROFILE_METADATA",
    "READ_RESOURCE_METADATA",
}
EMERGENCY_STOP_OPERATIONS = {
    "BLOCK_NEW_CALLS_FOR_EXACT_RUN",
    "CAS_EXACT_RUN_CAPABILITY_TO_STOP_FENCED",
    "CONFIRM_RETENTION_BINDINGS",
    "CONFIRM_ZERO_ACTIVE_LEASE_COMMITMENTS",
    "DISARM_EXACT_ASSIGNED_CUT",
    "FREEZE_EXACT_ASSIGNED_RESOURCES",
    "ISOLATE_EXACT_ASSIGNED_RUN_EGRESS",
    "PERSIST_CURRENT_ROW_DURABLE_STATE_AND_SAFE_EVIDENCE",
    "REDUCTIVE_TEARDOWN_WITHIN_EXACT_CLEANUP_SCOPE",
    "REVOKE_EXACT_RUN_CREDENTIAL_LEASES",
}
STOP_ONLY_ADAPTER_OPERATIONS = {
    operation
    for adapter in EXPECTED_ADAPTER_CATALOG.values()
    for operation in adapter.get("stop_only_operations", [])
}
EXPERIMENT_ADAPTER_OPERATIONS = {
    operation
    for adapter in EXPECTED_ADAPTER_CATALOG.values()
    for operation in adapter["allowed_operations"]
}
AUTHORITY_SHARED_BINDINGS = (
    "adapter_build_sha256",
    "adapter_set_manifest_sha256",
    "assignment_sha256",
    "cleanup_policy_sha256",
    "configuration_sha256",
    "contract_sha256",
    "cost_scope_sha256",
    "credential_scope_sha256",
    "offline_harness_manifest_sha256",
    "phase",
    "profile_sha256",
    "resource_scope_sha256",
    "retention_policy_sha256",
    "revocation_epoch",
    "namespace_id",
    "runner_build_sha256",
    "schedule_sha256",
    "simulation_run_id",
    "stop_control_plane_manifest_sha256",
    "suite_id",
    "track_id",
)
AUTHORITY_ROOT_INTERSECTION_BINDINGS = (
    "adapter_build_sha256",
    "adapter_set_manifest_sha256",
    "assignment_sha256",
    "cleanup_policy_sha256",
    "configuration_sha256",
    "contract_sha256",
    "cost_scope_sha256",
    "credential_scope_sha256",
    "effective_allowed_operations",
    "field_level_intersection_sha256",
    "namespace_id",
    "offline_harness_manifest_sha256",
    "phase",
    "profile_sha256",
    "resource_scope_sha256",
    "retention_policy_sha256",
    "revocation_epoch",
    "runner_build_sha256",
    "schedule_sha256",
    "simulation_run_id",
    "stop_control_plane_manifest_sha256",
    "suite_id",
    "track_id",
)
CAPABILITY_COMMITMENT_BINDING_FIELDS = (
    "adapter_build_sha256",
    "adapter_set_manifest_sha256",
    "assignment_sha256",
    "case_id",
    "channel_binding_sha256",
    "cleanup_policy_sha256",
    "configuration_sha256",
    "contract_sha256",
    "control_ledger_record_sha256",
    "cost_scope_sha256",
    "credential_scope_sha256",
    "effective_allowed_operations",
    "field_level_intersection_sha256",
    "namespace_id",
    "offline_harness_manifest_sha256",
    "phase",
    "profile_sha256",
    "repetition_index",
    "resource_scope_sha256",
    "retention_policy_sha256",
    "revocation_epoch",
    "runner_build_sha256",
    "schedule_sha256",
    "simulation_run_id",
    "single_consume",
    "single_executor_session",
    "single_run",
    "stop_control_plane_manifest_sha256",
    "suite_id",
    "track_id",
)


def _strict_utc_seconds(value: Any) -> bool:
    if type(value) is not str or re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
        value,
    ) is None:
        return False
    year = int(value[0:4])
    month = int(value[5:7])
    day = int(value[8:10])
    hour = int(value[11:13])
    minute = int(value[14:16])
    second = int(value[17:19])
    if not (
        year >= 1
        and 1 <= month <= 12
        and 0 <= hour <= 23
        and 0 <= minute <= 59
        and 0 <= second <= 59
    ):
        return False
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    month_days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return 1 <= day <= month_days[month - 1]


def _assignment_lineage(track_id: str, case_id: str, repetition_index: int) -> tuple[str, str, str]:
    cases = (
        tuple(f"M{index:02d}" for index in range(16))
        if track_id == MANAGED_TRACK
        else tuple(f"S{index:02d}" for index in range(18))
    )
    require(case_id in cases, "E_AUTHORITY_CASE_TRACK", "assignment case does not belong to track")
    require(1 <= repetition_index <= 30, "E_AUTHORITY_REPETITION", "assignment repetition outside 1..30")
    ordered = sorted(
        cases,
        key=lambda candidate: _framed_sha256(
            SCHEDULE_DOMAIN.encode("utf-8"),
            track_id.encode("utf-8"),
            repetition_index.to_bytes(4, "big"),
            candidate.encode("utf-8"),
        ),
    )
    assignment = {
        "configuration_sha256": EXPECTED_LINEAGE["offline_configuration_sha256"],
        "contract_sha256": EXPECTED_LINEAGE["preregistration_contract_sha256"],
        "domain": SCHEDULE_DOMAIN,
        "ordered_case_ids": ordered,
        "repetition_index": repetition_index,
        "track_id": track_id,
    }
    assignment_sha256 = sha256_value(assignment)
    simulation_run_id = _framed_sha256(
        RUN_DOMAIN.encode("utf-8"),
        track_id.encode("utf-8"),
        case_id.encode("utf-8"),
        repetition_index.to_bytes(4, "big"),
        bytes.fromhex(EXPECTED_LINEAGE["offline_configuration_sha256"]),
        bytes.fromhex(assignment_sha256),
    )
    namespace_id = _framed_sha256(
        NAMESPACE_DOMAIN.encode("utf-8"), bytes.fromhex(simulation_run_id)
    )
    return assignment_sha256, simulation_run_id, namespace_id


def _scope_payload_sha256(receipt: dict[str, Any]) -> str:
    payload = {
        key: copy.deepcopy(value)
        for key, value in receipt.items()
        if key not in {"canonical_payload_sha256", "receipt_id", "signature_receipt_sha256"}
    }
    return _domain_canonical_hash(SCOPE_RECEIPT_PAYLOAD_DOMAIN, payload)


def _scope_receipt_id(receipt: dict[str, Any]) -> str:
    return _framed_sha256(
        SCOPE_RECEIPT_ID_DOMAIN.encode("utf-8"),
        receipt["artifact_type"].encode("utf-8"),
        bytes.fromhex(receipt["canonical_payload_sha256"]),
        bytes.fromhex(receipt["signature_receipt_sha256"]),
    )


def _authority_intersection_sha256(intersection: dict[str, Any]) -> str:
    payload = {
        key: copy.deepcopy(value)
        for key, value in intersection.items()
        if key != "field_level_intersection_sha256"
    }
    return _domain_canonical_hash(AUTHORITY_INTERSECTION_DOMAIN, payload)


def _authority_bundle_id(bundle: dict[str, Any]) -> str:
    payload = {key: copy.deepcopy(value) for key, value in bundle.items() if key != "bundle_id"}
    return _domain_canonical_hash(AUTHORITY_BUNDLE_ID_DOMAIN, payload)


def _private_capability_commitment(private_bytes: bytes, capability: dict[str, Any]) -> str:
    require(len(private_bytes) == 32, "E_AUTHORITY_CAPABILITY", "KAT private capability length drift")
    binding = {
        key: copy.deepcopy(capability[key])
        for key in CAPABILITY_COMMITMENT_BINDING_FIELDS
    }
    return _framed_sha256(
        PRIVATE_CAPABILITY_DOMAIN.encode("utf-8"),
        private_bytes,
        canonical_bytes(binding),
    )


def _kat_scope_receipt(
    artifact_type: str,
    ordinal: int,
    assignment_sha256: str,
    simulation_run_id: str,
    namespace_id: str,
) -> dict[str, Any]:
    emergency = artifact_type == "EMERGENCY_STOP_AUTHORITY_RECEIPT"
    receipt = {
        "adapter_build_sha256": _kat_hash("adapter-build"),
        "adapter_set_manifest_sha256": _kat_hash("adapter-set"),
        "allowed_case_ids": ["M00"],
        "allowed_operations": (
            ["BLOCK_NEW_CALLS_FOR_EXACT_RUN"]
            if emergency
            else ["STRONG_READ_EXACT_OPERATION_KEY"]
        ),
        "allowed_repetition_indices": [1],
        "artifact_type": artifact_type,
        "assignment_sha256": assignment_sha256,
        "authority_principal_id_sha256": _kat_hash(f"principal-{ordinal}"),
        "authorization_request_sha256": _kat_hash(f"authorization-request-{ordinal}"),
        "canonical_payload_sha256": "0" * 64,
        "cleanup_policy_sha256": _kat_hash("cleanup-policy"),
        "configuration_sha256": EXPECTED_LINEAGE["offline_configuration_sha256"],
        "contract_sha256": EXPECTED_CONTRACT_SHA256,
        "cost_scope_sha256": _kat_hash("cost-scope"),
        "credential_scope_sha256": _kat_hash("credential-scope"),
        "expires_at_utc": "2026-07-15T21:00:00Z",
        "forbidden_operations": ["OUTPUT_AUTHORIZATION"],
        "issued_at_utc": "2026-07-15T19:00:00Z",
        "namespace_id": namespace_id,
        "nonce_sha256": _kat_hash(f"nonce-{ordinal}"),
        "not_before_utc": "2026-07-15T19:30:00Z",
        "offline_harness_manifest_sha256": EXPECTED_LINEAGE["offline_harness_manifest_sha256"],
        "phase": "EXPERIMENT_EXECUTION_GRANT",
        "profile_sha256": _kat_hash("profile"),
        "receipt_id": "0" * 64,
        "receipt_is_output_permit": False,
        "resource_scope_sha256": _kat_hash("resource-scope"),
        "retention_policy_sha256": _kat_hash("retention-policy"),
        "revocation_epoch": 7,
        "runner_build_sha256": _kat_hash("runner-build"),
        "schedule_sha256": EXPECTED_LINEAGE["offline_schedule_sha256"],
        "signature_receipt_sha256": _kat_hash(f"signature-{ordinal}"),
        "simulation_run_id": simulation_run_id,
        "stop_control_plane_manifest_sha256": _kat_hash("stop-control-plane"),
        "suite_id": OFFLINE_SUITE_ID,
        "track_id": MANAGED_TRACK,
        "trust_policy_sha256": _kat_hash(f"trust-policy-{ordinal}"),
    }
    receipt["canonical_payload_sha256"] = _scope_payload_sha256(receipt)
    receipt["receipt_id"] = _scope_receipt_id(receipt)
    return receipt


def authority_kat_instance() -> dict[str, Any]:
    assignment_sha256, simulation_run_id, namespace_id = _assignment_lineage(
        MANAGED_TRACK, "M00", 1
    )
    receipts = {
        slot: _kat_scope_receipt(
            artifact_type, ordinal, assignment_sha256, simulation_run_id, namespace_id
        )
        for ordinal, (slot, artifact_type) in enumerate(AUTHORITY_SLOT_TYPES.items(), start=1)
    }
    intersection = {
        "adapter_build_sha256": _kat_hash("adapter-build"),
        "adapter_set_manifest_sha256": _kat_hash("adapter-set"),
        "assignment_sha256": assignment_sha256,
        "cleanup_policy_sha256": _kat_hash("cleanup-policy"),
        "configuration_sha256": EXPECTED_LINEAGE["offline_configuration_sha256"],
        "contract_sha256": EXPECTED_CONTRACT_SHA256,
        "cost_scope_sha256": _kat_hash("cost-scope"),
        "credential_scope_sha256": _kat_hash("credential-scope"),
        "effective_allowed_case_ids": ["M00"],
        "effective_allowed_operations": ["STRONG_READ_EXACT_OPERATION_KEY"],
        "effective_allowed_repetition_indices": [1],
        "field_level_intersection_sha256": "0" * 64,
        "namespace_id": namespace_id,
        "nonempty_exact_intersection": True,
        "offline_harness_manifest_sha256": EXPECTED_LINEAGE["offline_harness_manifest_sha256"],
        "phase": "EXPERIMENT_EXECUTION_GRANT",
        "profile_sha256": _kat_hash("profile"),
        "resource_scope_sha256": _kat_hash("resource-scope"),
        "retention_policy_sha256": _kat_hash("retention-policy"),
        "revocation_epoch": 7,
        "runner_build_sha256": _kat_hash("runner-build"),
        "schedule_sha256": EXPECTED_LINEAGE["offline_schedule_sha256"],
        "simulation_run_id": simulation_run_id,
        "stop_control_plane_manifest_sha256": _kat_hash("stop-control-plane"),
        "suite_id": OFFLINE_SUITE_ID,
        "track_id": MANAGED_TRACK,
    }
    intersection["field_level_intersection_sha256"] = _authority_intersection_sha256(
        intersection
    )
    capability = {
        "adapter_build_sha256": intersection["adapter_build_sha256"],
        "adapter_set_manifest_sha256": intersection["adapter_set_manifest_sha256"],
        "assignment_sha256": assignment_sha256,
        "capability_commitment_sha256": "0" * 64,
        "case_id": "M00",
        "channel_binding_sha256": _kat_hash("channel-binding"),
        "cleanup_policy_sha256": intersection["cleanup_policy_sha256"],
        "configuration_sha256": intersection["configuration_sha256"],
        "contract_sha256": EXPECTED_CONTRACT_SHA256,
        "control_ledger_record_sha256": _kat_hash("control-ledger"),
        "cost_scope_sha256": intersection["cost_scope_sha256"],
        "credential_scope_sha256": intersection["credential_scope_sha256"],
        "effective_allowed_operations": list(intersection["effective_allowed_operations"]),
        "field_level_intersection_sha256": intersection["field_level_intersection_sha256"],
        "namespace_id": namespace_id,
        "offline_harness_manifest_sha256": intersection["offline_harness_manifest_sha256"],
        "phase": intersection["phase"],
        "private_capability_bytes_serialized": False,
        "profile_sha256": intersection["profile_sha256"],
        "repetition_index": 1,
        "resource_scope_sha256": intersection["resource_scope_sha256"],
        "retention_policy_sha256": intersection["retention_policy_sha256"],
        "revocation_epoch": 7,
        "runner_build_sha256": intersection["runner_build_sha256"],
        "schedule_sha256": intersection["schedule_sha256"],
        "simulation_run_id": simulation_run_id,
        "single_consume": True,
        "single_executor_session": True,
        "single_run": True,
        "state": "UNUSED",
        "stop_control_plane_manifest_sha256": intersection["stop_control_plane_manifest_sha256"],
        "suite_id": OFFLINE_SUITE_ID,
        "track_id": MANAGED_TRACK,
    }
    capability["capability_commitment_sha256"] = _private_capability_commitment(
        bytes(range(32)), capability
    )
    bundle = {
        "adapter_build_sha256": intersection["adapter_build_sha256"],
        "adapter_set_manifest_sha256": intersection["adapter_set_manifest_sha256"],
        "assignment_sha256": assignment_sha256,
        "authority_intersection": intersection,
        "bundle_id": "0" * 64,
        "case_id": "M00",
        "cleanup_policy_sha256": intersection["cleanup_policy_sha256"],
        "condition_output_authorized": False,
        "configuration_sha256": intersection["configuration_sha256"],
        "contract_sha256": EXPECTED_CONTRACT_SHA256,
        "cost_authority_receipt": receipts["cost_authority_receipt"],
        "cost_scope_sha256": intersection["cost_scope_sha256"],
        "credential_scope_sha256": intersection["credential_scope_sha256"],
        "currentness": {
            "checked_at_utc": "2026-07-15T20:00:00Z",
            "cost_budget_reserved": True,
            "credential_lease_current": True,
            "profile_current": True,
            "resource_budget_reserved": True,
            "revocation_epoch": 7,
            "row_currentness_receipt_sha256": _kat_hash("row-currentness"),
            "trusted_time_receipt_sha256": _kat_hash("trusted-time"),
        },
        "custodian_credential_receipt": receipts["custodian_credential_receipt"],
        "effective_allowed_operations": list(intersection["effective_allowed_operations"]),
        "emergency_stop_authority_receipt": receipts["emergency_stop_authority_receipt"],
        "execution_capability_commitment": capability,
        "field_level_intersection_sha256": intersection["field_level_intersection_sha256"],
        "namespace_id": namespace_id,
        "offline_harness_manifest_sha256": intersection["offline_harness_manifest_sha256"],
        "owner_scope_receipt": receipts["owner_scope_receipt"],
        "phase": intersection["phase"],
        "profile_sha256": intersection["profile_sha256"],
        "public_bundle_is_bearer_capability": False,
        "receipt_is_output_permit": False,
        "repetition_index": 1,
        "resource_authority_receipt": receipts["resource_authority_receipt"],
        "resource_scope_sha256": intersection["resource_scope_sha256"],
        "retention_policy_sha256": intersection["retention_policy_sha256"],
        "revocation_epoch": 7,
        "runner_build_sha256": intersection["runner_build_sha256"],
        "schedule_sha256": intersection["schedule_sha256"],
        "schema": AUTHORITY_RECEIPT_SCHEMA,
        "simulation_run_id": simulation_run_id,
        "stop_control_plane_manifest_sha256": intersection["stop_control_plane_manifest_sha256"],
        "suite_id": OFFLINE_SUITE_ID,
        "track_id": MANAGED_TRACK,
    }
    bundle["bundle_id"] = _authority_bundle_id(bundle)
    return bundle


def validate_authority_bundle_instance(bundle: dict[str, Any], schema: dict[str, Any]) -> None:
    validate_json_schema(bundle, schema)
    require(bundle["bundle_id"] == _authority_bundle_id(bundle), "E_AUTHORITY_BUNDLE_ID", "authority bundle id preimage mismatch")
    require(bundle["condition_output_authorized"] is False, "E_AUTHORITY_OUTPUT", "condition output authorized")
    require(bundle["receipt_is_output_permit"] is False, "E_AUTHORITY_OUTPUT", "authority is output permit")
    require(bundle["public_bundle_is_bearer_capability"] is False, "E_AUTHORITY_CAPABILITY", "public bundle is bearer capability")
    track = bundle["track_id"]
    phase = bundle["phase"]
    require(track in {MANAGED_TRACK, SELF_HOSTED_TRACK}, "E_AUTHORITY_TRACK", "authority track drift")
    require(phase in {"PREFLIGHT_OBSERVATION_GRANT", "EXPERIMENT_EXECUTION_GRANT"}, "E_AUTHORITY_PHASE", "authority phase drift")
    intersection = bundle["authority_intersection"]
    capability = bundle["execution_capability_commitment"]
    for field in AUTHORITY_ROOT_INTERSECTION_BINDINGS:
        require_equal(bundle[field], intersection[field], "E_AUTHORITY_ROOT_BINDING", field)
        require_equal(capability[field], intersection[field], "E_AUTHORITY_CAP_BINDING", field)
    require(capability["case_id"] == bundle["case_id"] and capability["repetition_index"] == bundle["repetition_index"], "E_AUTHORITY_CAP_BINDING", "capability assignment mismatch")
    require(capability["private_capability_bytes_serialized"] is False, "E_AUTHORITY_CAPABILITY", "private capability serialized")
    require(capability["single_consume"] is True and capability["single_executor_session"] is True and capability["single_run"] is True, "E_AUTHORITY_CAPABILITY", "capability is reusable")
    require(capability["state"] == "UNUSED", "E_AUTHORITY_CAPABILITY", "new capability not unused")
    require(capability["capability_commitment_sha256"] == _private_capability_commitment(bytes(range(32)), capability), "E_AUTHORITY_CAPABILITY_HASH", "KAT capability commitment preimage mismatch")
    currentness = bundle["currentness"]
    require(_strict_utc_seconds(currentness["checked_at_utc"]), "E_AUTHORITY_CURRENTNESS", "currentness timestamp malformed")
    for field in ("cost_budget_reserved", "credential_lease_current", "profile_current", "resource_budget_reserved"):
        require(currentness[field] is True, "E_AUTHORITY_CURRENTNESS", f"currentness {field} is not true")
    require(bundle["revocation_epoch"] == currentness["revocation_epoch"], "E_AUTHORITY_REVOCATION", "root/currentness epoch mismatch")
    require(bundle["contract_sha256"] == EXPECTED_CONTRACT_SHA256, "E_AUTHORITY_CONTRACT_BINDING", "contract binding drift")
    require(bundle["configuration_sha256"] == EXPECTED_LINEAGE["offline_configuration_sha256"], "E_AUTHORITY_CONFIGURATION_BINDING", "configuration binding drift")
    require(bundle["offline_harness_manifest_sha256"] == EXPECTED_LINEAGE["offline_harness_manifest_sha256"], "E_AUTHORITY_MANIFEST_BINDING", "manifest binding drift")
    require(bundle["schedule_sha256"] == EXPECTED_LINEAGE["offline_schedule_sha256"], "E_AUTHORITY_SCHEDULE_BINDING", "schedule binding drift")
    require(bundle["suite_id"] == OFFLINE_SUITE_ID, "E_AUTHORITY_SUITE_BINDING", "suite binding drift")
    expected_assignment, expected_run, expected_namespace = _assignment_lineage(
        track, bundle["case_id"], bundle["repetition_index"]
    )
    require(bundle["assignment_sha256"] == expected_assignment, "E_AUTHORITY_ASSIGNMENT_HASH", "assignment lineage drift")
    require(bundle["simulation_run_id"] == expected_run, "E_AUTHORITY_RUN_HASH", "run lineage drift")
    require(bundle["namespace_id"] == expected_namespace, "E_AUTHORITY_NAMESPACE_HASH", "namespace lineage drift")
    receipts = [bundle[slot] for slot in AUTHORITY_SLOT_TYPES]
    principals: set[str] = set()
    receipt_ids: set[str] = set()
    nonces: set[str] = set()
    requests: set[str] = set()
    signatures: set[str] = set()
    allowed_case_sets: list[set[str]] = []
    allowed_operation_sets: list[set[str]] = []
    allowed_repetition_sets: list[set[int]] = []
    forbidden_union: set[str] = set()
    valid_cases = (
        {f"M{index:02d}" for index in range(16)}
        if track == MANAGED_TRACK
        else {f"S{index:02d}" for index in range(18)}
    )
    for receipt, (slot, expected_type) in zip(receipts, AUTHORITY_SLOT_TYPES.items()):
        require(receipt["artifact_type"] == expected_type, "E_AUTHORITY_ROLE", f"{slot} role mismatch")
        for field in AUTHORITY_SHARED_BINDINGS:
            require_equal(receipt[field], intersection[field], "E_AUTHORITY_BINDING", f"{slot}.{field}")
        require(receipt["receipt_is_output_permit"] is False, "E_AUTHORITY_OUTPUT", f"{slot} is output permit")
        for field in ("issued_at_utc", "not_before_utc", "expires_at_utc"):
            require(_strict_utc_seconds(receipt[field]), "E_AUTHORITY_TIME", f"{slot}.{field} malformed")
        checked = currentness["checked_at_utc"]
        require(receipt["issued_at_utc"] <= receipt["not_before_utc"] < receipt["expires_at_utc"], "E_AUTHORITY_TIME", f"{slot} receipt time order invalid")
        require(receipt["not_before_utc"] <= checked < receipt["expires_at_utc"], "E_AUTHORITY_CURRENTNESS", f"{slot} outside current window")
        require(receipt["revocation_epoch"] == currentness["revocation_epoch"], "E_AUTHORITY_REVOCATION", f"{slot} epoch mismatch")
        for field in ("allowed_case_ids", "allowed_operations", "allowed_repetition_indices", "forbidden_operations"):
            require(receipt[field] == sorted(receipt[field]), "E_AUTHORITY_CANONICAL_SCOPE", f"{slot}.{field} not sorted")
        require(set(receipt["allowed_operations"]).isdisjoint(receipt["forbidden_operations"]), "E_AUTHORITY_OPERATION_SCOPE", f"{slot} allowed/forbidden overlap")
        require(all(case_id in valid_cases for case_id in receipt["allowed_case_ids"]), "E_AUTHORITY_CASE_TRACK", f"{slot} case crosses track")
        require(receipt["canonical_payload_sha256"] == _scope_payload_sha256(receipt), "E_AUTHORITY_PAYLOAD_HASH", f"{slot} payload preimage mismatch")
        require(receipt["receipt_id"] == _scope_receipt_id(receipt), "E_AUTHORITY_RECEIPT_ID", f"{slot} id preimage mismatch")
        allowed_case_sets.append(set(receipt["allowed_case_ids"]))
        allowed_operation_sets.append(set(receipt["allowed_operations"]))
        allowed_repetition_sets.append(set(receipt["allowed_repetition_indices"]))
        forbidden_union.update(receipt["forbidden_operations"])
        principals.add(receipt["authority_principal_id_sha256"])
        receipt_ids.add(receipt["receipt_id"])
        nonces.add(receipt["nonce_sha256"])
        requests.add(receipt["authorization_request_sha256"])
        signatures.add(receipt["signature_receipt_sha256"])
    require(all(len(values) == 5 for values in (principals, receipt_ids, nonces, requests, signatures)), "E_AUTHORITY_INDEPENDENCE", "five roles are not independent")
    exact_cases = set.intersection(*allowed_case_sets)
    exact_repetitions = set.intersection(*allowed_repetition_sets)
    exact_operations = set.intersection(*allowed_operation_sets[:4]) - forbidden_union
    for actual, expected, label in (
        (intersection["effective_allowed_case_ids"], exact_cases, "case ids"),
        (intersection["effective_allowed_repetition_indices"], exact_repetitions, "repetitions"),
        (intersection["effective_allowed_operations"], exact_operations, "operations"),
    ):
        require(actual == sorted(actual) and set(actual) == expected and len(actual) == len(expected) and bool(actual), "E_AUTHORITY_EXACT_INTERSECTION", f"effective {label} is not exact nonempty intersection")
    emergency = receipts[4]
    require(set(emergency["allowed_operations"]).issubset(EMERGENCY_STOP_OPERATIONS), "E_EMERGENCY_SCOPE", "emergency receipt adds experiment operation")
    require(set(intersection["effective_allowed_operations"]).isdisjoint(emergency["allowed_operations"]), "E_EMERGENCY_SCOPE", "emergency allowed operation added positive authority")
    require(intersection["field_level_intersection_sha256"] == _authority_intersection_sha256(intersection), "E_AUTHORITY_INTERSECTION_HASH", "intersection preimage mismatch")
    if phase == "EXPERIMENT_EXECUTION_GRANT":
        require(intersection["effective_allowed_case_ids"] == [bundle["case_id"]], "E_AUTHORITY_ASSIGNMENT", "execution case not singleton assignment")
        require(intersection["effective_allowed_repetition_indices"] == [bundle["repetition_index"]], "E_AUTHORITY_ASSIGNMENT", "execution repetition not singleton assignment")
        require(set(intersection["effective_allowed_operations"]).issubset(EXPERIMENT_ADAPTER_OPERATIONS), "E_AUTHORITY_OPERATION_CATALOG", "execution operation outside adapter catalog")
        require(set(intersection["effective_allowed_operations"]).isdisjoint(STOP_ONLY_ADAPTER_OPERATIONS), "E_AUTHORITY_STOP_ONLY", "stop-only operation authorized for experiment")
    else:
        require(set(intersection["effective_allowed_operations"]).issubset(PREFLIGHT_OPERATIONS), "E_AUTHORITY_PREFLIGHT", "preflight operation outside read-only catalog")


def _legacy_stop_kat_instance() -> dict[str, Any]:
    return {
        "application_calls": 1,
        "authority_bundle_sha256": _kat_hash("bundle"),
        "automatic_rerun_allowed": False,
        "case_id": "M00",
        "cleanup": {
            "cleanup_capability_commitment_sha256": _kat_hash("cleanup-capability"),
            "cleanup_completed_at_utc": "2026-07-15T20:06:00Z",
            "cleanup_status": "REDUCTIVE_COMPLETE",
            "egress_isolated": True,
            "resource_frozen": True,
        },
        "continuation_allowed": False,
        "cost": {
            "actual_cost_minor_units": 1,
            "cost_authority_receipt_sha256": _kat_hash("cost-receipt"),
            "currency": "USD",
            "remaining_authorized_minor_units": 9,
        },
        "credential": {
            "active_lease_commitments_after_stop": 0,
            "revoke_confirmed": True,
            "revoke_receipt_sha256": _kat_hash("revoke"),
            "revoke_requested": True,
            "revoke_status": "REVOKED",
        },
        "current_retained_row_sha256": _kat_hash("retained-row"),
        "durable_state": {
            "authority_currentness_receipt_sha256": _kat_hash("currentness"),
            "call_state_sha256": _kat_hash("call-state"),
            "control_ledger_revision": 5,
            "operation_record_sha256": _kat_hash("operation"),
            "prepared_state_sha256": _kat_hash("prepared"),
        },
        "evidence_bundle_sha256": _kat_hash("evidence"),
        "fault": {
            "disarm_confirmed": True,
            "disarm_receipt_sha256": _kat_hash("disarm"),
            "disarm_requested": True,
            "disarm_status": "DISARMED",
            "fault_controller_state_sha256": _kat_hash("fault-state"),
        },
        "last_completed_row_sha256": None,
        "manual_escalation_required": True,
        "profile_sha256": _kat_hash("profile"),
        "receipt_is_execution_authority": False,
        "receipt_is_output_permit": False,
        "repetition_index": 1,
        "resource_scope_sha256": _kat_hash("resource-scope"),
        "run_id": _kat_hash("run-id"),
        "schema": STOP_RECEIPT_SCHEMA,
        "stop_completed_at_utc": "2026-07-15T20:07:00Z",
        "stop_id": _kat_hash("stop"),
        "stop_reason": "UNRESOLVED_AMBIGUITY",
        "stop_requested_at_utc": "2026-07-15T20:05:00Z",
        "stop_trigger_role": "SYSTEM_BOUNDARY",
        "suite_id": _kat_hash("suite"),
        "track_id": MANAGED_TRACK,
        "unresolved_ambiguity_ids": [_kat_hash("ambiguity")],
        "wire_attempts": 1,
    }


def _legacy_validate_stop_receipt_instance(receipt: dict[str, Any], schema: dict[str, Any]) -> None:
    validate_json_schema(receipt, schema)
    require(receipt["continuation_allowed"] is False and receipt["automatic_rerun_allowed"] is False, "E_STOP_ABSORPTION", "stop permits continuation")
    expected_prefix = "M" if receipt["track_id"] == MANAGED_TRACK else "S"
    require(receipt["case_id"].startswith(expected_prefix), "E_STOP_CASE_TRACK", "stop case crosses track")
    require(receipt["stop_requested_at_utc"] <= (receipt["stop_completed_at_utc"] or "9999"), "E_STOP_TIME", "stop completion precedes request")
    completed = receipt["stop_completed_at_utc"] is not None
    if completed:
        require(receipt["cleanup"]["cleanup_status"] == "REDUCTIVE_COMPLETE", "E_STOP_COMPLETION", "completed stop cleanup not complete")
        require(receipt["credential"]["revoke_confirmed"] is True and receipt["credential"]["revoke_status"] == "REVOKED", "E_STOP_COMPLETION", "completed stop credential revoke unconfirmed")
        require(receipt["fault"]["disarm_confirmed"] is True and receipt["fault"]["disarm_status"] == "DISARMED", "E_STOP_COMPLETION", "completed stop fault disarm unconfirmed")
        require(receipt["cleanup"]["resource_frozen"] is True and receipt["cleanup"]["egress_isolated"] is True, "E_STOP_COMPLETION", "completed stop is not isolated")
    else:
        require(
            receipt["cleanup"]["cleanup_status"] in {"NOT_STARTED", "REDUCTIVE_IN_PROGRESS", "FAILED_QUARANTINED"}
            or not receipt["credential"]["revoke_confirmed"]
            or not receipt["fault"]["disarm_confirmed"],
            "E_STOP_INCOMPLETE",
            "fully terminal stop omitted completion time",
        )
    if receipt["credential"]["revoke_confirmed"]:
        require(receipt["credential"]["revoke_requested"] is True and receipt["credential"]["revoke_receipt_sha256"] is not None and receipt["credential"]["active_lease_commitments_after_stop"] == 0 and receipt["credential"]["revoke_status"] == "REVOKED", "E_STOP_REVOKE", "revoke confirmation is unbound")
    require((receipt["credential"]["revoke_status"] == "REVOKED") is receipt["credential"]["revoke_confirmed"], "E_STOP_REVOKE", "revoke status/confirmation contradiction")
    if receipt["fault"]["disarm_confirmed"]:
        require(receipt["fault"]["disarm_requested"] is True and receipt["fault"]["disarm_receipt_sha256"] is not None and receipt["fault"]["disarm_status"] == "DISARMED", "E_STOP_DISARM", "disarm confirmation is unbound")
    require((receipt["fault"]["disarm_status"] == "DISARMED") is receipt["fault"]["disarm_confirmed"], "E_STOP_DISARM", "disarm status/confirmation contradiction")
    if receipt["unresolved_ambiguity_ids"] or receipt["cleanup"]["cleanup_status"] == "FAILED_QUARANTINED":
        require(receipt["manual_escalation_required"] is True, "E_STOP_ESCALATION", "unresolved stop lacks escalation")


def _stop_receipt_id(receipt: dict[str, Any]) -> str:
    payload = {
        key: copy.deepcopy(value)
        for key, value in receipt.items()
        if key not in {"signature_receipt_sha256", "stop_id"}
    }
    return _domain_canonical_hash(STOP_RECEIPT_ID_DOMAIN, payload)


def stop_kat_instance(authority: dict[str, Any] | None = None) -> dict[str, Any]:
    authority = authority_kat_instance() if authority is None else authority
    intersection = authority["authority_intersection"]
    receipt = {
        "adapter_build_sha256": authority["adapter_build_sha256"],
        "adapter_set_manifest_sha256": authority["adapter_set_manifest_sha256"],
        "application_calls": 1,
        "assignment_sha256": authority["assignment_sha256"],
        "authority_bundle_sha256": sha256_value(authority),
        "authority_phase": authority["phase"],
        "authority_revocation_epoch": authority["revocation_epoch"],
        "automatic_rerun_allowed": False,
        "capability_fence_receipt_sha256": _kat_hash("capability-fence"),
        "capability_invalidated": True,
        "case_id": authority["case_id"],
        "cleanup": {
            "cleanup_capability_commitment_sha256": _kat_hash("cleanup-capability"),
            "cleanup_completed_at_utc": "2026-07-15T20:06:00Z",
            "cleanup_receipt_sha256": _kat_hash("cleanup-receipt"),
            "cleanup_status": "REDUCTIVE_COMPLETE",
            "egress_isolated": True,
            "egress_isolation_receipt_sha256": _kat_hash("egress-isolation"),
            "resource_frozen": True,
        },
        "cleanup_policy_sha256": intersection["cleanup_policy_sha256"],
        "configuration_sha256": authority["configuration_sha256"],
        "continuation_allowed": False,
        "contract_sha256": authority["contract_sha256"],
        "control_plane_failure_ids": [],
        "cost": {
            "actual_cost_minor_units": 1,
            "cost_authority_receipt_sha256": sha256_value(authority["cost_authority_receipt"]),
            "currency": "USD",
            "remaining_authorized_minor_units": 9,
        },
        "cost_scope_sha256": intersection["cost_scope_sha256"],
        "credential": {
            "active_lease_commitments_after_stop": 0,
            "revoke_confirmed": True,
            "revoke_receipt_sha256": _kat_hash("revoke-receipt"),
            "revoke_requested": True,
            "revoke_status": "REVOKED",
        },
        "credential_scope_sha256": intersection["credential_scope_sha256"],
        "current_retained_row_sha256": _kat_hash("current-retained-row"),
        "durable_state": {
            "authority_currentness_receipt_sha256": authority["currentness"]["row_currentness_receipt_sha256"],
            "call_state_sha256": _kat_hash("call-state"),
            "control_ledger_revision": 5,
            "operation_record_sha256": _kat_hash("operation-record"),
            "prepared_state_sha256": _kat_hash("prepared-state"),
        },
        "evidence_bundle_sha256": _kat_hash("evidence-bundle"),
        "evidence_preserved": True,
        "fault": {
            "disarm_confirmed": True,
            "disarm_receipt_sha256": _kat_hash("disarm-receipt"),
            "disarm_requested": True,
            "disarm_status": "DISARMED",
            "fault_controller_state_sha256": _kat_hash("fault-controller-state"),
        },
        "field_level_intersection_sha256": intersection["field_level_intersection_sha256"],
        "last_completed_row_sha256": None,
        "manual_escalation_required": False,
        "namespace_id": authority["namespace_id"],
        "new_calls_blocked": True,
        "offline_harness_manifest_sha256": authority["offline_harness_manifest_sha256"],
        "profile_sha256": authority["profile_sha256"],
        "receipt_is_execution_authority": False,
        "receipt_is_output_permit": False,
        "repetition_index": authority["repetition_index"],
        "resource_scope_sha256": intersection["resource_scope_sha256"],
        "retained_row_preserved": True,
        "retention_policy_sha256": intersection["retention_policy_sha256"],
        "retention_receipt_sha256": _kat_hash("retention-receipt"),
        "runner_build_sha256": authority["runner_build_sha256"],
        "schedule_sha256": authority["schedule_sha256"],
        "schema": STOP_RECEIPT_SCHEMA,
        "signature_receipt_sha256": _kat_hash("stop-signature-receipt"),
        "simulation_run_id": authority["simulation_run_id"],
        "stop_completed_at_utc": "2026-07-15T20:07:00Z",
        "stop_control_plane_manifest_sha256": authority["stop_control_plane_manifest_sha256"],
        "stop_id": "0" * 64,
        "stop_lifecycle_state": "STOP_ABSORBING_COMPLETE",
        "stop_reason": "OPERATOR_STOP",
        "stop_requested_at_utc": "2026-07-15T20:05:00Z",
        "stop_trigger": "OWNER_CUSTODIAN_OR_EMERGENCY_OPERATOR_STOP",
        "stop_trigger_role": "OWNER",
        "suite_id": authority["suite_id"],
        "track_id": authority["track_id"],
        "unresolved_ambiguity_ids": [],
        "wire_attempts": 1,
    }
    receipt["stop_id"] = _stop_receipt_id(receipt)
    return receipt


def validate_stop_receipt_instance(
    receipt: dict[str, Any],
    schema: dict[str, Any],
    authority: dict[str, Any] | None = None,
) -> None:
    validate_json_schema(receipt, schema)
    require(receipt["stop_id"] == _stop_receipt_id(receipt), "E_STOP_ID", "stop id preimage mismatch")
    track = receipt["track_id"]
    valid_cases = (
        {f"M{index:02d}" for index in range(16)}
        if track == MANAGED_TRACK
        else {f"S{index:02d}" for index in range(18)}
    )
    require(track in {MANAGED_TRACK, SELF_HOSTED_TRACK} and receipt["case_id"] in valid_cases, "E_STOP_CASE_TRACK", "stop case crosses track")
    require(receipt["contract_sha256"] == EXPECTED_CONTRACT_SHA256, "E_STOP_CONTRACT_BINDING", "stop contract binding drift")
    require(receipt["configuration_sha256"] == EXPECTED_LINEAGE["offline_configuration_sha256"], "E_STOP_CONFIGURATION_BINDING", "stop configuration binding drift")
    require(receipt["offline_harness_manifest_sha256"] == EXPECTED_LINEAGE["offline_harness_manifest_sha256"], "E_STOP_MANIFEST_BINDING", "stop manifest binding drift")
    require(receipt["schedule_sha256"] == EXPECTED_LINEAGE["offline_schedule_sha256"], "E_STOP_SCHEDULE_BINDING", "stop schedule binding drift")
    require(receipt["suite_id"] == OFFLINE_SUITE_ID, "E_STOP_SUITE_BINDING", "stop suite binding drift")
    assignment, simulation_run_id, namespace_id = _assignment_lineage(
        track, receipt["case_id"], receipt["repetition_index"]
    )
    require(receipt["assignment_sha256"] == assignment, "E_STOP_ASSIGNMENT_HASH", "stop assignment lineage drift")
    require(receipt["simulation_run_id"] == simulation_run_id, "E_STOP_RUN_HASH", "stop run lineage drift")
    require(receipt["namespace_id"] == namespace_id, "E_STOP_NAMESPACE_HASH", "stop namespace lineage drift")
    require(receipt["authority_phase"] == "EXPERIMENT_EXECUTION_GRANT", "E_STOP_PHASE", "stop authority phase is not execution")
    mapping = EXPECTED_TRIGGER_REASON_ROLE_MAP[receipt["stop_trigger"]]
    require(receipt["stop_reason"] in mapping["reasons"], "E_STOP_TRIGGER_REASON", "stop reason does not match trigger")
    require(receipt["stop_trigger_role"] in mapping["roles"], "E_STOP_TRIGGER_ROLE", "stop role does not match trigger")
    for field in ("capability_invalidated", "evidence_preserved", "new_calls_blocked", "retained_row_preserved"):
        require(receipt[field] is True, "E_STOP_ABSORPTION", f"stop {field} is not true")
    for field in ("automatic_rerun_allowed", "continuation_allowed", "receipt_is_execution_authority", "receipt_is_output_permit"):
        require(receipt[field] is False, "E_STOP_ABSORPTION", f"stop {field} is not false")
    requested_at = receipt["stop_requested_at_utc"]
    completed_at = receipt["stop_completed_at_utc"]
    cleanup = receipt["cleanup"]
    credential = receipt["credential"]
    fault = receipt["fault"]
    require(_strict_utc_seconds(requested_at), "E_STOP_TIME", "stop request timestamp malformed")
    cleanup_at = cleanup["cleanup_completed_at_utc"]
    if cleanup_at is not None:
        require(_strict_utc_seconds(cleanup_at) and requested_at <= cleanup_at, "E_STOP_TIME", "cleanup time invalid")
    if completed_at is not None:
        require(_strict_utc_seconds(completed_at) and requested_at <= completed_at, "E_STOP_TIME", "stop completion time invalid")
        require(cleanup_at is not None and cleanup_at <= completed_at, "E_STOP_TIME", "stop completed before cleanup")
    cleanup_terminal = cleanup["cleanup_status"] in {"REDUCTIVE_COMPLETE", "FAILED_QUARANTINED"}
    require((cleanup_at is not None) is cleanup_terminal, "E_STOP_CLEANUP", "cleanup time/status contradiction")
    require((cleanup["cleanup_receipt_sha256"] is not None) is cleanup_terminal, "E_STOP_CLEANUP", "cleanup receipt/status contradiction")
    if cleanup_terminal:
        require(cleanup["egress_isolated"] is True and cleanup["egress_isolation_receipt_sha256"] is not None and cleanup["resource_frozen"] is True, "E_STOP_CLEANUP", "terminal cleanup lacks isolation/fence")
    credential_expected = {
        "NOT_REQUESTED": (False, False, False),
        "PENDING": (True, False, False),
        "REVOKED": (True, True, True),
        "FAILED_QUARANTINED": (True, False, True),
    }[credential["revoke_status"]]
    require((credential["revoke_requested"], credential["revoke_confirmed"], credential["revoke_receipt_sha256"] is not None) == credential_expected, "E_STOP_REVOKE", "credential stop state contradiction")
    if credential["revoke_confirmed"]:
        require(credential["active_lease_commitments_after_stop"] == 0, "E_STOP_REVOKE", "revoked credential retains active lease")
    fault_expected = {
        "NOT_REQUESTED": (False, False, False),
        "PENDING": (True, False, False),
        "DISARMED": (True, True, True),
        "FAILED_QUARANTINED": (True, False, True),
    }[fault["disarm_status"]]
    require((fault["disarm_requested"], fault["disarm_confirmed"], fault["disarm_receipt_sha256"] is not None) == fault_expected, "E_STOP_DISARM", "fault stop state contradiction")
    failures = bool(receipt["unresolved_ambiguity_ids"] or receipt["control_plane_failure_ids"])
    failures = failures or cleanup["cleanup_status"] == "FAILED_QUARANTINED"
    failures = failures or credential["revoke_status"] == "FAILED_QUARANTINED"
    failures = failures or fault["disarm_status"] == "FAILED_QUARANTINED"
    all_success = (
        cleanup["cleanup_status"] == "REDUCTIVE_COMPLETE"
        and credential["revoke_status"] == "REVOKED"
        and fault["disarm_status"] == "DISARMED"
        and not failures
    )
    state = receipt["stop_lifecycle_state"]
    require((state == "STOP_ABSORBING_COMPLETE") is all_success, "E_STOP_COMPLETION", "absorbing-complete converse violated")
    require((state == "STOP_FAILED_QUARANTINED") is failures, "E_STOP_FAILURE", "failed-quarantined converse violated")
    if state == "STOP_ABSORBING_COMPLETE":
        require(completed_at is not None and receipt["manual_escalation_required"] is False, "E_STOP_COMPLETION", "complete stop completion/escalation drift")
    else:
        require(completed_at is None, "E_STOP_COMPLETION", "noncomplete stop has completion timestamp")
    if failures:
        require(receipt["manual_escalation_required"] is True, "E_STOP_ESCALATION", "failed stop lacks escalation")
    if authority is not None:
        intersection = authority["authority_intersection"]
        authority_mapping = {
            "adapter_build_sha256": authority["adapter_build_sha256"],
            "adapter_set_manifest_sha256": authority["adapter_set_manifest_sha256"],
            "assignment_sha256": authority["assignment_sha256"],
            "authority_bundle_sha256": sha256_value(authority),
            "authority_phase": authority["phase"],
            "authority_revocation_epoch": authority["revocation_epoch"],
            "case_id": authority["case_id"],
            "cleanup_policy_sha256": intersection["cleanup_policy_sha256"],
            "configuration_sha256": authority["configuration_sha256"],
            "contract_sha256": authority["contract_sha256"],
            "cost_scope_sha256": intersection["cost_scope_sha256"],
            "credential_scope_sha256": intersection["credential_scope_sha256"],
            "field_level_intersection_sha256": intersection["field_level_intersection_sha256"],
            "namespace_id": authority["namespace_id"],
            "offline_harness_manifest_sha256": authority["offline_harness_manifest_sha256"],
            "profile_sha256": authority["profile_sha256"],
            "repetition_index": authority["repetition_index"],
            "resource_scope_sha256": intersection["resource_scope_sha256"],
            "retention_policy_sha256": intersection["retention_policy_sha256"],
            "runner_build_sha256": authority["runner_build_sha256"],
            "schedule_sha256": authority["schedule_sha256"],
            "simulation_run_id": authority["simulation_run_id"],
            "stop_control_plane_manifest_sha256": authority["stop_control_plane_manifest_sha256"],
            "suite_id": authority["suite_id"],
            "track_id": authority["track_id"],
        }
        for field, expected in authority_mapping.items():
            require_equal(receipt[field], expected, "E_STOP_AUTHORITY_BINDING", field)
        require(receipt["cost"]["cost_authority_receipt_sha256"] == sha256_value(authority["cost_authority_receipt"]), "E_STOP_AUTHORITY_BINDING", "cost authority receipt mismatch")
        require(receipt["durable_state"]["authority_currentness_receipt_sha256"] == authority["currentness"]["row_currentness_receipt_sha256"], "E_STOP_AUTHORITY_BINDING", "currentness receipt mismatch")


def validate_synthetic_observation(observation: dict[str, Any]) -> None:
    exact_keys(
        observation,
        (
            "audit_scope",
            "authority",
            "boundary",
            "inventory",
            "lineage",
            "observation_class",
            "observed_at_utc",
            "planned_counts",
            "runtime_counts",
            "schema",
        ),
        "E_OBSERVATION_FIELDS",
        "synthetic observation",
    )
    require(observation["schema"] == OBSERVATION_SCHEMA, "E_OBSERVATION_SCHEMA", "observation schema drift")
    require(observation["observation_class"] == "UNBOUND_SYNTHETIC_PACKET_AUDIT", "E_OBSERVATION_CLASS", "observation class drift")
    require(observation["observed_at_utc"] == "2026-07-15T20:00:00Z", "E_OBSERVATION_TIME", "observation timestamp drift")
    require_equal(
        observation["audit_scope"],
        {
            "external_organization_state_observed": False,
            "host_visibility_complete": False,
            "network_observed": False,
            "repository_scope": "CURRENT_PACKET_AND_FROZEN_PREDECESSOR_ARTIFACTS_ONLY",
            "secret_values_inspected_or_recorded": False,
        },
        "E_OBSERVATION_AUDIT",
        "observation audit scope",
    )
    authority = observation["authority"]
    exact_keys(
        authority,
        (
            "authority_bundles_bound",
            "cost_authority_receipts_bound",
            "credential_authority_receipts_bound",
            "custodian_scope_receipts_bound",
            "emergency_stop_authority_receipts_bound",
            "execution_capabilities_emitted",
            "owner_scope_receipts_bound",
            "phase",
            "resource_authority_receipts_bound",
            "row_currentness_receipts_bound",
        ),
        "E_OBSERVATION_AUTHORITY",
        "observation authority",
    )
    require(authority["phase"] == "UNBOUND_SYNTHETIC", "E_OBSERVATION_AUTHORITY", "synthetic authority phase drift")
    for key, value in authority.items():
        if key != "phase":
            require(type(value) is int and value == 0, "E_OBSERVATION_AUTHORITY", f"synthetic authority {key} must be zero")
    require_equal(observation["boundary"], EXPECTED_OBSERVATION_BOUNDARY, "E_OBSERVATION_BOUNDARY", "synthetic boundary")
    inventory = observation["inventory"]
    expected_inventory_keys = {
        "adapter_artifacts",
        "credential_handles",
        "endpoints",
        "execution_runs",
        "provider_profiles",
        "resource_bindings",
        "runtime_receipts",
        "stop_receipts",
    }
    exact_keys(inventory, expected_inventory_keys, "E_OBSERVATION_INVENTORY", "synthetic inventory")
    for key, value in inventory.items():
        require(value == [], "E_OBSERVATION_INVENTORY", f"synthetic inventory {key} must be empty")
    require_equal(observation["lineage"], EXPECTED_LINEAGE, "E_OBSERVATION_LINEAGE", "synthetic lineage")
    require_equal(
        observation["planned_counts"],
        {
            "client_conformance_double_rows": 420,
            "managed_cases": 16,
            "managed_service_fault_proxy_rows": 210,
            "planned_rows": 1020,
            "self_hosted_adversarial_lab_rows": 390,
            "self_hosted_cases": 18,
            "tracks": 2,
        },
        "E_OBSERVATION_PLANNED",
        "synthetic planned counts",
    )
    runtime = observation["runtime_counts"]
    exact_keys(
        runtime,
        (
            "application_calls",
            "evaluable_case_rows",
            "provider_evidence_rows",
            "provider_processing_events",
            "retained_rows",
            "runtime_rows",
            "wire_attempts",
        ),
        "E_OBSERVATION_RUNTIME",
        "synthetic runtime counts",
    )
    for key, value in runtime.items():
        require(type(value) is int and value == 0, "E_OBSERVATION_RUNTIME", f"synthetic runtime {key} must be zero")


def validate_contract_semantics(
    adapter_contract: dict[str, Any],
    authority_schema: dict[str, Any],
    stop_schema: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    """Validate all frozen semantics without delegating to the source module."""

    validate_adapter_contract(adapter_contract)
    validate_authority_schema_semantics(authority_schema)
    validate_stop_schema_semantics(stop_schema)
    validate_synthetic_observation(observation)
    authority = authority_kat_instance()
    validate_authority_bundle_instance(authority, authority_schema)
    stop = stop_kat_instance(authority)
    validate_stop_receipt_instance(stop, stop_schema, authority)
    return {
        "artifact_sha256": {
            "adapter_contract": sha256_value(adapter_contract),
            "authority_receipt_schema": sha256_value(authority_schema),
            "observation": sha256_value(observation),
            "stop_receipt_schema": sha256_value(stop_schema),
        },
        "authority_model": {
            "capability": "PRIVATE_NONSERIALIZABLE_SINGLE_RUN_SINGLE_SESSION_SINGLE_CONSUMPTION",
            "start_logic": "START_ALL_FIVE_CURRENT_OWNER_CUSTODIAN_RESOURCE_COST_INTERSECTION_WITH_EMERGENCY_VETO",
            "stop_logic": "STOP_OWNER_OR_CUSTODIAN_OR_EMERGENCY_OR_BOUNDARY_OR_EXPIRY",
        },
        "baseline_commit": BASELINE_COMMIT,
        "boundary": copy.deepcopy(observation["boundary"]),
        "data_quality": {
            "contract_closure": "PASS",
            "execution_evidence": "NOT_EVALUATED_ZERO_RUNTIME_ROWS",
            "schema_closure": "PASS",
            "synthetic_observation": "PASS_UNBOUND_ZERO_RUNTIME",
        },
        "date": "2026-07-15",
        "decision": DECISION,
        "next_unit": NEXT_UNIT,
        "planned_counts": copy.deepcopy(observation["planned_counts"]),
        "schema": VALIDATION_RECEIPT_SCHEMA,
        "status": STATUS,
        "track_results": {
            MANAGED_TRACK: "CONTRACT_VALIDATED_RUNTIME_UNBOUND",
            SELF_HOSTED_TRACK: "CONTRACT_VALIDATED_RUNTIME_UNBOUND",
        },
    }


def _replace_at(value: Any, path: tuple[Any, ...], replacement: Any) -> Any:
    result = copy.deepcopy(value)
    current = result
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = replacement
    return result


def _delete_at(value: Any, path: tuple[Any, ...]) -> Any:
    result = copy.deepcopy(value)
    current = result
    for part in path[:-1]:
        current = current[part]
    del current[path[-1]]
    return result


def _rebind_authority_receipt(bundle: dict[str, Any], slot: str) -> None:
    receipt = bundle[slot]
    receipt["canonical_payload_sha256"] = _scope_payload_sha256(receipt)
    receipt["receipt_id"] = _scope_receipt_id(receipt)
    bundle["bundle_id"] = _authority_bundle_id(bundle)


def _rebind_authority_intersection(bundle: dict[str, Any]) -> None:
    intersection = bundle["authority_intersection"]
    intersection["field_level_intersection_sha256"] = _authority_intersection_sha256(
        intersection
    )
    bundle["bundle_id"] = _authority_bundle_id(bundle)


def _rebind_capability(bundle: dict[str, Any]) -> None:
    capability = bundle["execution_capability_commitment"]
    capability["capability_commitment_sha256"] = _private_capability_commitment(
        bytes(range(32)), capability
    )
    bundle["bundle_id"] = _authority_bundle_id(bundle)


def _rebind_stop(receipt: dict[str, Any]) -> None:
    receipt["stop_id"] = _stop_receipt_id(receipt)


def run_directed_negative_tests(
    adapter_contract: dict[str, Any],
    authority_schema: dict[str, Any],
    stop_schema: dict[str, Any],
    observation: dict[str, Any],
    source_module: Any,
) -> int:
    """Run a stable P0 mutation matrix against independent and source oracles."""

    count = run_loader_self_tests()

    def reject(label: str, call: Callable[[], None]) -> None:
        nonlocal count
        _expect_failure(call, label)
        count += 1

    # Contract closure, authority algebra, routing loci, evidence, adapters,
    # credential isolation, predecessor lineage, stop controls, and sources.
    contract_mutations: list[tuple[str, dict[str, Any]]] = []
    contract_paths = (
        (("start_stop_logic", "start", "combination"), "OR_ANY_TRIGGER"),
        (("start_stop_logic", "stop", "combination"), "AND_ALL_REQUIRED"),
        (("authority_model", "artifact_count"), 4),
        (("authority_model", "wildcard_or_parent_resource_scope_allowed"), True),
        (("authority_model", "capability", "serialization_allowed"), True),
        (("authority_model", "capability", "cross_run_reuse_allowed"), True),
        (("authority_model", "emergency_stop_scope", "positive_execution_authority_added"), True),
        (("adapter_interfaces", "managed", "adapter_count"), 3),
        (("adapter_interfaces", "self_hosted", "adapter_count"), 4),
        (("adapter_interfaces", "client_conformance_route", "row_count"), 419),
        (("execution_plan", "counts", "planned_rows"), 1019),
        (("execution_plan", "case_routing", "CLIENT_CONFORMANCE_DOUBLE", "rows"), 419),
        (("execution_plan", "case_routing", "MANAGED_SERVICE_WITH_CLIENT_FAULT_PROXY", "rows"), 209),
        (("execution_plan", "case_routing", "SELF_HOSTED_ADVERSARIAL_LAB", "rows"), 389),
        (("retained_row_contract", "retained"), False),
        (("retained_row_contract", "case_classification_null_for_nonevaluable_row"), False),
        (("credential_isolation", "ambient_or_default_credential_chain_allowed"), True),
        (("credential_isolation", "runner_secret_visibility_allowed"), True),
        (("credential_isolation", "cross_adapter_handle_reuse_allowed"), True),
        (("credential_isolation", "stop_control_handles_reusable_for_experiment"), True),
        (("boundary", "provider_called"), True),
        (("boundary", "credentials_accessed"), True),
        (("stop_control_plane", "interface_count"), 4),
        (("stop_control_plane", "shared_execution_credential_allowed"), True),
        (("predecessor", "offline_harness_manifest_sha256"), _kat_hash("wrong-manifest")),
        (("official_source_claims", 0, "retrieved_on"), "2026-07-14"),
        (("official_source_claims", 0, "url"), "https://invalid.example/"),
    )
    for index, (path, replacement) in enumerate(contract_paths):
        contract_mutations.append((f"contract-path-{index}", _replace_at(adapter_contract, path, replacement)))
    contract_mutations.extend(
        [
            ("contract-start-condition-drop", _replace_at(adapter_contract, ("start_stop_logic", "start", "conditions"), adapter_contract["start_stop_logic"]["start"]["conditions"][:-1])),
            ("contract-stop-trigger-drop", _replace_at(adapter_contract, ("start_stop_logic", "stop", "triggers"), adapter_contract["start_stop_logic"]["stop"]["triggers"][:-1])),
            ("contract-authority-artifact-drop", _replace_at(adapter_contract, ("authority_model", "artifacts"), adapter_contract["authority_model"]["artifacts"][:-1])),
            ("contract-s12-branch-drop", _delete_at(adapter_contract, ("s12_branch_contract", "correlated_postwire_failure_branch"))),
            ("contract-official-source-drop", _replace_at(adapter_contract, ("official_source_claims",), adapter_contract["official_source_claims"][:-1])),
        ]
    )
    managed_fault = next(index for index, item in enumerate(adapter_contract["adapter_interfaces"]["managed"]["adapters"]) if item["adapter_id"] == "MANAGED_FAULT_PROXY_ADAPTER")
    evidence_collector = next(index for index, item in enumerate(adapter_contract["adapter_interfaces"]["managed"]["adapters"]) if item["adapter_id"] == "MANAGED_EVIDENCE_COLLECTOR_ADAPTER")
    contract_mutations.extend(
        [
            ("contract-adapter-operation-extra", _replace_at(adapter_contract, ("adapter_interfaces", "managed", "adapters", 0, "allowed_operations"), adapter_contract["adapter_interfaces"]["managed"]["adapters"][0]["allowed_operations"] + ["AMBIENT_PROVIDER_CALL"])),
            ("contract-adapter-evidence-drop", _replace_at(adapter_contract, ("adapter_interfaces", "managed", "adapters", 0, "evidence_returns"), adapter_contract["adapter_interfaces"]["managed"]["adapters"][0]["evidence_returns"][:-1])),
            ("contract-adapter-classification", _replace_at(adapter_contract, ("adapter_interfaces", "managed", "adapters", evidence_collector, "forbidden_operations"), ["CREDENTIAL_MATERIAL_CAPTURE", "OUTPUT_AUTHORIZATION"])),
            ("contract-stop-authorizes-experiment", _replace_at(adapter_contract, ("adapter_interfaces", "managed", "adapters", managed_fault, "stop_capability_may_authorize_experiment"), True)),
            ("contract-stop-credential-shared", _replace_at(adapter_contract, ("adapter_interfaces", "managed", "adapters", managed_fault, "stop_only_credential_class"), "MANAGED_FAULT_PROXY_CONTROL")),
        ]
    )
    for label, mutation in contract_mutations:
        reject(label + "-independent", lambda mutation=mutation: validate_adapter_contract(mutation, bind_hash=False))
        reject(label + "-source", lambda mutation=mutation: source_module.validate_contract(mutation))

    # Meta-schema closure and exact catalogs, including role narrowing.
    schema_mutations: list[tuple[str, dict[str, Any], Callable[[dict[str, Any]], None], Callable[[dict[str, Any]], None]]] = []
    authority_schema_paths = (
        (("additionalProperties",), True),
        (("type",), "array"),
        (("properties", "repetition_index", "minimum"), 0),
        (("properties", "repetition_index", "maximum"), 31),
        (("$defs", "scope_receipt", "additionalProperties"), True),
        (("$defs", "scope_receipt", "type"), "array"),
        (("$defs", "scope_receipt", "properties", "allowed_repetition_indices", "items", "minimum"), 0),
        (("$defs", "execution_capability_commitment", "properties", "single_consume", "const"), False),
        (("$defs", "owner_scope_receipt", "allOf", 1, "properties", "artifact_type", "const"), "COST_AUTHORITY_RECEIPT"),
    )
    for index, (path, replacement) in enumerate(authority_schema_paths):
        schema_mutations.append((f"authority-schema-{index}", _replace_at(authority_schema, path, replacement), lambda value: validate_authority_schema_semantics(value, bind_hash=False), source_module.validate_authority_schema))
    narrowing_typo = copy.deepcopy(authority_schema)
    narrowing_typo["$defs"]["owner_scope_receipt"]["allOf"][1]["properties"]["artifact_typo"] = narrowing_typo["$defs"]["owner_scope_receipt"]["allOf"][1]["properties"].pop("artifact_type")
    narrowing_typo["$defs"]["owner_scope_receipt"]["allOf"][1]["required"] = ["artifact_typo"]
    schema_mutations.append(("authority-schema-narrowing-typo", narrowing_typo, lambda value: validate_authority_schema_semantics(value, bind_hash=False), source_module.validate_authority_schema))
    schema_mutations.append(("authority-schema-required-drop", _replace_at(authority_schema, ("required",), authority_schema["required"][:-1]), lambda value: validate_authority_schema_semantics(value, bind_hash=False), source_module.validate_authority_schema))
    stop_schema_paths = (
        (("additionalProperties",), True),
        (("type",), "array"),
        (("properties", "repetition_index", "minimum"), 0),
        (("properties", "repetition_index", "maximum"), 31),
        (("$defs", "cleanup", "additionalProperties"), True),
        (("$defs", "cleanup", "type"), "array"),
        (("properties", "automatic_rerun_allowed", "const"), True),
        (("properties", "capability_invalidated", "const"), False),
    )
    for index, (path, replacement) in enumerate(stop_schema_paths):
        schema_mutations.append((f"stop-schema-{index}", _replace_at(stop_schema, path, replacement), lambda value: validate_stop_schema_semantics(value, bind_hash=False), source_module.validate_stop_schema))
    schema_mutations.append(("stop-schema-role-drop", _replace_at(stop_schema, ("properties", "stop_trigger_role", "enum"), [role for role in stop_schema["properties"]["stop_trigger_role"]["enum"] if role != "EMERGENCY_OPERATOR"]), lambda value: validate_stop_schema_semantics(value, bind_hash=False), source_module.validate_stop_schema))
    schema_mutations.append(("stop-schema-guard-drop", _replace_at(stop_schema, ("allOf",), stop_schema["allOf"][:-5]), lambda value: validate_stop_schema_semantics(value, bind_hash=False), source_module.validate_stop_schema))
    schema_mutations.append(("stop-schema-required-drop", _replace_at(stop_schema, ("required",), stop_schema["required"][:-1]), lambda value: validate_stop_schema_semantics(value, bind_hash=False), source_module.validate_stop_schema))
    for label, mutation, independent, source in schema_mutations:
        reject(label + "-independent", lambda mutation=mutation, independent=independent: independent(mutation))
        reject(label + "-source", lambda mutation=mutation, source=source: source(mutation))

    # Authority bundle root/intersection/capability and all five role receipts.
    authority = authority_kat_instance()
    authority_validator = lambda value: validate_authority_bundle_instance(value, authority_schema)
    root_fields = AUTHORITY_ROOT_INTERSECTION_BINDINGS + ("case_id", "repetition_index")
    for field in root_fields:
        mutation = copy.deepcopy(authority)
        value = mutation[field]
        if type(value) is str:
            mutation[field] = "PREFLIGHT_OBSERVATION_GRANT" if field == "phase" else _kat_hash(f"wrong-root-{field}")
        elif type(value) is int:
            mutation[field] = value + 1
        else:
            mutation[field] = ["LINEARIZABLE_EXACT_READ"]
        mutation["bundle_id"] = _authority_bundle_id(mutation)
        reject(f"authority-root-{field}", lambda mutation=mutation: authority_validator(mutation))
    receipt_binding_fields = (
        "track_id", "phase", "suite_id", "simulation_run_id", "namespace_id",
        "assignment_sha256", "contract_sha256", "configuration_sha256", "schedule_sha256",
        "runner_build_sha256", "adapter_build_sha256", "adapter_set_manifest_sha256",
        "stop_control_plane_manifest_sha256", "resource_scope_sha256", "credential_scope_sha256",
        "cost_scope_sha256", "retention_policy_sha256", "cleanup_policy_sha256", "revocation_epoch",
    )
    slots = list(AUTHORITY_SLOT_TYPES)
    for slot in slots:
        for field in receipt_binding_fields:
            mutation = copy.deepcopy(authority)
            value = mutation[slot][field]
            mutation[slot][field] = value + 1 if type(value) is int else ("PREFLIGHT_OBSERVATION_GRANT" if field == "phase" else _kat_hash(f"wrong-{slot}-{field}"))
            _rebind_authority_receipt(mutation, slot)
            reject(f"authority-receipt-{slot}-{field}", lambda mutation=mutation: authority_validator(mutation))
    role_values = list(AUTHORITY_SLOT_TYPES.values())
    for index, slot in enumerate(slots):
        mutation = copy.deepcopy(authority)
        mutation[slot]["artifact_type"] = role_values[(index + 1) % len(role_values)]
        _rebind_authority_receipt(mutation, slot)
        reject(f"authority-role-swap-{slot}", lambda mutation=mutation: authority_validator(mutation))
    for field in AUTHORITY_ROOT_INTERSECTION_BINDINGS:
        mutation = copy.deepcopy(authority)
        value = mutation["execution_capability_commitment"][field]
        mutation["execution_capability_commitment"][field] = ["LINEARIZABLE_EXACT_READ"] if type(value) is list else (value + 1 if type(value) is int else ("PREFLIGHT_OBSERVATION_GRANT" if field == "phase" else _kat_hash(f"wrong-cap-{field}")))
        _rebind_capability(mutation)
        reject(f"authority-capability-{field}", lambda mutation=mutation: authority_validator(mutation))
    for field in AUTHORITY_SHARED_BINDINGS:
        mutation = copy.deepcopy(authority)
        value = mutation["authority_intersection"][field]
        mutation["authority_intersection"][field] = value + 1 if type(value) is int else ("PREFLIGHT_OBSERVATION_GRANT" if field == "phase" else _kat_hash(f"wrong-intersection-{field}"))
        _rebind_authority_intersection(mutation)
        reject(f"authority-intersection-{field}", lambda mutation=mutation: authority_validator(mutation))
    authority_specials: list[tuple[str, dict[str, Any]]] = []
    for field, replacement in (
        ("condition_output_authorized", True),
        ("receipt_is_output_permit", True),
        ("public_bundle_is_bearer_capability", True),
    ):
        mutation = copy.deepcopy(authority); mutation[field] = replacement; mutation["bundle_id"] = _authority_bundle_id(mutation); authority_specials.append((field, mutation))
    for field, replacement in (
        ("private_capability_bytes_serialized", True),
        ("single_consume", False),
        ("single_executor_session", False),
        ("single_run", False),
        ("state", "CONSUMED"),
    ):
        mutation = copy.deepcopy(authority); mutation["execution_capability_commitment"][field] = replacement; mutation["bundle_id"] = _authority_bundle_id(mutation); authority_specials.append(("cap-" + field, mutation))
    mutation = copy.deepcopy(authority); mutation["bundle_id"] = _kat_hash("wrong-bundle-id"); authority_specials.append(("bundle-id-preimage", mutation))
    mutation = copy.deepcopy(authority); mutation["execution_capability_commitment"]["capability_commitment_sha256"] = _kat_hash("wrong-capability"); mutation["bundle_id"] = _authority_bundle_id(mutation); authority_specials.append(("capability-preimage", mutation))
    mutation = copy.deepcopy(authority); mutation["currentness"]["credential_lease_current"] = False; mutation["bundle_id"] = _authority_bundle_id(mutation); authority_specials.append(("currentness-false", mutation))
    mutation = copy.deepcopy(authority); mutation["currentness"]["revocation_epoch"] = 8; mutation["bundle_id"] = _authority_bundle_id(mutation); authority_specials.append(("revocation-epoch", mutation))
    mutation = copy.deepcopy(authority); mutation["owner_scope_receipt"]["not_before_utc"] = "2026-02-30T19:30:00Z"; _rebind_authority_receipt(mutation, "owner_scope_receipt"); authority_specials.append(("february-30", mutation))
    mutation = copy.deepcopy(authority); mutation["owner_scope_receipt"]["issued_at_utc"] = "2026-07-15T19:45:00Z"; _rebind_authority_receipt(mutation, "owner_scope_receipt"); authority_specials.append(("time-reverse", mutation))
    mutation = copy.deepcopy(authority); mutation["owner_scope_receipt"]["canonical_payload_sha256"] = _kat_hash("wrong-payload"); mutation["bundle_id"] = _authority_bundle_id(mutation); authority_specials.append(("payload-preimage", mutation))
    mutation = copy.deepcopy(authority); mutation["owner_scope_receipt"]["receipt_id"] = _kat_hash("wrong-receipt-id"); mutation["bundle_id"] = _authority_bundle_id(mutation); authority_specials.append(("receipt-id-preimage", mutation))
    mutation = copy.deepcopy(authority); mutation["owner_scope_receipt"]["forbidden_operations"] = sorted(["OUTPUT_AUTHORIZATION", "STRONG_READ_EXACT_OPERATION_KEY"]); _rebind_authority_receipt(mutation, "owner_scope_receipt"); authority_specials.append(("allowed-forbidden-overlap", mutation))
    mutation = copy.deepcopy(authority); mutation["emergency_stop_authority_receipt"]["allowed_operations"] = ["STRONG_READ_EXACT_OPERATION_KEY"]; _rebind_authority_receipt(mutation, "emergency_stop_authority_receipt"); authority_specials.append(("emergency-positive-operation", mutation))
    for field, replacement in (("effective_allowed_case_ids", ["M00", "M01"]), ("effective_allowed_repetition_indices", [1, 2])):
        mutation = copy.deepcopy(authority); mutation["authority_intersection"][field] = replacement; _rebind_authority_intersection(mutation); authority_specials.append(("false-intersection-" + field, mutation))
    mutation = copy.deepcopy(authority)
    mutation["authority_intersection"]["effective_allowed_operations"] = ["LINEARIZABLE_EXACT_READ"]
    mutation["authority_intersection"]["field_level_intersection_sha256"] = _authority_intersection_sha256(mutation["authority_intersection"])
    mutation["effective_allowed_operations"] = ["LINEARIZABLE_EXACT_READ"]
    mutation["field_level_intersection_sha256"] = mutation["authority_intersection"]["field_level_intersection_sha256"]
    mutation["execution_capability_commitment"]["effective_allowed_operations"] = ["LINEARIZABLE_EXACT_READ"]
    mutation["execution_capability_commitment"]["field_level_intersection_sha256"] = mutation["field_level_intersection_sha256"]
    _rebind_capability(mutation)
    authority_specials.append(("false-intersection-operations", mutation))
    for label, mutation in authority_specials:
        reject("authority-" + label, lambda mutation=mutation: authority_validator(mutation))
    for repetition in (0, 31):
        mutation = copy.deepcopy(authority); mutation["repetition_index"] = repetition; mutation["bundle_id"] = _authority_bundle_id(mutation)
        reject(f"authority-repetition-{repetition}", lambda mutation=mutation: authority_validator(mutation))

    # Stop receipt: exact authority binding, absorbing lifecycle, trigger map,
    # terminal component state, timestamps, and non-continuation.
    stop = stop_kat_instance(authority)
    stop_validator = lambda value: validate_stop_receipt_instance(value, stop_schema, authority)
    stop_binding_fields = (
        "adapter_build_sha256", "adapter_set_manifest_sha256", "assignment_sha256",
        "authority_bundle_sha256", "authority_revocation_epoch", "case_id",
        "cleanup_policy_sha256", "configuration_sha256", "contract_sha256",
        "cost_scope_sha256", "credential_scope_sha256", "field_level_intersection_sha256",
        "namespace_id", "offline_harness_manifest_sha256", "profile_sha256",
        "repetition_index", "resource_scope_sha256", "retention_policy_sha256",
        "runner_build_sha256", "schedule_sha256", "simulation_run_id",
        "stop_control_plane_manifest_sha256", "suite_id", "track_id",
    )
    for field in stop_binding_fields:
        mutation = copy.deepcopy(stop); value = mutation[field]
        mutation[field] = value + 1 if type(value) is int else _kat_hash(f"wrong-stop-{field}")
        _rebind_stop(mutation)
        reject(f"stop-authority-binding-{field}", lambda mutation=mutation: stop_validator(mutation))
    stop_specials: list[tuple[str, dict[str, Any]]] = []
    for field, replacement in (
        ("automatic_rerun_allowed", True), ("continuation_allowed", True),
        ("receipt_is_execution_authority", True), ("receipt_is_output_permit", True),
        ("capability_invalidated", False), ("new_calls_blocked", False),
        ("evidence_preserved", False), ("retained_row_preserved", False),
    ):
        mutation = copy.deepcopy(stop); mutation[field] = replacement; _rebind_stop(mutation); stop_specials.append((field, mutation))
    mutation = copy.deepcopy(stop); mutation["stop_id"] = _kat_hash("wrong-stop-id"); stop_specials.append(("id-preimage", mutation))
    mutation = copy.deepcopy(stop); mutation["case_id"] = "M99"; _rebind_stop(mutation); stop_specials.append(("invalid-case", mutation))
    mutation = copy.deepcopy(stop); mutation["stop_requested_at_utc"] = "2026-02-30T20:05:00Z"; _rebind_stop(mutation); stop_specials.append(("february-30", mutation))
    mutation = copy.deepcopy(stop); mutation["cleanup"]["cleanup_completed_at_utc"] = "2026-07-15T20:04:59Z"; _rebind_stop(mutation); stop_specials.append(("cleanup-time-reverse", mutation))
    mutation = copy.deepcopy(stop); mutation["stop_completed_at_utc"] = "2026-07-15T20:05:59Z"; _rebind_stop(mutation); stop_specials.append(("completion-before-cleanup", mutation))
    mutation = copy.deepcopy(stop); mutation["stop_reason"] = "AUTHORITY_REVOKED"; _rebind_stop(mutation); stop_specials.append(("trigger-reason-mismatch", mutation))
    mutation = copy.deepcopy(stop); mutation["stop_trigger_role"] = "SYSTEM_BOUNDARY"; _rebind_stop(mutation); stop_specials.append(("trigger-role-mismatch", mutation))
    mutation = copy.deepcopy(stop); mutation["stop_lifecycle_state"] = "STOP_FENCING"; _rebind_stop(mutation); stop_specials.append(("false-fencing", mutation))
    mutation = copy.deepcopy(stop); mutation["cleanup"]["cleanup_status"] = "REDUCTIVE_IN_PROGRESS"; _rebind_stop(mutation); stop_specials.append(("cleanup-incomplete", mutation))
    mutation = copy.deepcopy(stop); mutation["credential"]["revoke_confirmed"] = False; _rebind_stop(mutation); stop_specials.append(("revoke-confirmation-false", mutation))
    mutation = copy.deepcopy(stop); mutation["credential"]["revoke_requested"] = False; _rebind_stop(mutation); stop_specials.append(("revoke-request-false", mutation))
    mutation = copy.deepcopy(stop); mutation["credential"]["active_lease_commitments_after_stop"] = 1; _rebind_stop(mutation); stop_specials.append(("active-lease-after-stop", mutation))
    mutation = copy.deepcopy(stop); mutation["fault"]["disarm_confirmed"] = False; _rebind_stop(mutation); stop_specials.append(("disarm-confirmation-false", mutation))
    mutation = copy.deepcopy(stop); mutation["fault"]["disarm_requested"] = False; _rebind_stop(mutation); stop_specials.append(("disarm-request-false", mutation))
    mutation = copy.deepcopy(stop); mutation["control_plane_failure_ids"] = [_kat_hash("control-failure")]; _rebind_stop(mutation); stop_specials.append(("hidden-control-failure", mutation))
    mutation = copy.deepcopy(stop); mutation["unresolved_ambiguity_ids"] = [_kat_hash("ambiguity")]; _rebind_stop(mutation); stop_specials.append(("hidden-ambiguity", mutation))
    for label, mutation in stop_specials:
        reject("stop-" + label, lambda mutation=mutation: stop_validator(mutation))
    emergency_stop = copy.deepcopy(stop); emergency_stop["stop_trigger_role"] = "EMERGENCY_OPERATOR"; _rebind_stop(emergency_stop); stop_validator(emergency_stop)
    require(_strict_utc_seconds("2024-02-29T00:00:00Z"), "E_CALENDAR_KAT", "valid leap day rejected")
    require(not _strict_utc_seconds("2026-02-30T00:00:00Z") and not _strict_utc_seconds("0000-01-01T00:00:00Z"), "E_CALENDAR_KAT", "invalid calendar accepted")

    # Synthetic zero-runtime boundary: every runtime counter, authority,
    # inventory, audit, lineage, and public boundary remain fail-closed.
    observation_mutations: list[tuple[str, dict[str, Any]]] = []
    for field in observation["runtime_counts"]:
        observation_mutations.append(("runtime-" + field, _replace_at(observation, ("runtime_counts", field), 1)))
    observation_mutations.extend(
        [
            ("authority-capability", _replace_at(observation, ("authority", "execution_capabilities_emitted"), 1)),
            ("inventory-credential", _replace_at(observation, ("inventory", "credential_handles"), ["forbidden"])),
            ("audit-network", _replace_at(observation, ("audit_scope", "network_observed"), True)),
            ("boundary-provider", _replace_at(observation, ("boundary", "provider_called"), True)),
            ("lineage-manifest", _replace_at(observation, ("lineage", "offline_harness_manifest_sha256"), _kat_hash("wrong-lineage"))),
            ("planned-count", _replace_at(observation, ("planned_counts", "planned_rows"), 1019)),
        ]
    )
    for label, mutation in observation_mutations:
        reject("observation-" + label + "-independent", lambda mutation=mutation: validate_synthetic_observation(mutation))
        reject("observation-" + label + "-source", lambda mutation=mutation: source_module.validate_observation(mutation))
    return count


def validate_manifest(
    root: Path,
    manifest: dict[str, Any],
    receipt: dict[str, Any],
    negative_count: int,
) -> None:
    exact_keys(
        manifest,
        (
            "boundary", "date", "decision", "evidence_sha256",
            "logical_baseline_commit", "next_unit", "packet", "predecessor",
            "results", "schema", "status", "test_oracle", "tracks",
        ),
        "E_MANIFEST_FIELDS",
        "manifest",
    )
    require(manifest["schema"] == MANIFEST_SCHEMA, "E_MANIFEST_SCHEMA", "manifest schema drift")
    require(manifest["date"] == "2026-07-15", "E_MANIFEST_DATE", "manifest date drift")
    require(manifest["status"] == STATUS and manifest["decision"] == DECISION, "E_MANIFEST_DECISION", "manifest status/decision drift")
    require(manifest["logical_baseline_commit"] == BASELINE_COMMIT, "E_MANIFEST_BASELINE", "manifest baseline drift")
    require(manifest["next_unit"] == NEXT_UNIT, "E_MANIFEST_NEXT", "manifest next unit drift")
    require_equal(manifest["boundary"], receipt["boundary"], "E_MANIFEST_BOUNDARY", "manifest boundary")
    require_equal(
        manifest["predecessor"],
        {
            "integration_commit": BASELINE_COMMIT,
            "manifest_path": str(PREDECESSOR_PATHS[7]),
            "manifest_sha256": EXPECTED_PREDECESSOR_SHA256[str(PREDECESSOR_PATHS[7])],
            "source_commit": PREDECESSOR_SOURCE_COMMIT,
        },
        "E_MANIFEST_PREDECESSOR",
        "manifest predecessor",
    )
    expected_paths = [str(path) for path in PACKET_PATHS]
    expected_modes = {
        str(path): "100755" if path == GATE_PATH else "100644" for path in PACKET_PATHS
    }
    require_equal(manifest["packet"], {"modes": expected_modes, "paths": expected_paths}, "E_MANIFEST_PACKET", "manifest packet")
    evidence_paths = (
        ADAPTER_CONTRACT_PATH,
        AUTHORITY_SCHEMA_PATH,
        STOP_SCHEMA_PATH,
        SOURCE_PATH,
        CHECKER_PATH,
        SYNTHETIC_PATH,
        EXPECTED_PATH,
        REPORT_PATH,
        *PREDECESSOR_PATHS,
    )
    expected_evidence: dict[str, str] = {}
    for path in evidence_paths:
        try:
            expected_evidence[str(path)] = sha256_bytes((root / path).read_bytes())
        except OSError as exc:
            fail("E_MANIFEST_FILE", f"cannot read evidence artifact {path}: {exc}")
    require_equal(manifest["evidence_sha256"], expected_evidence, "E_MANIFEST_EVIDENCE", "manifest evidence hashes")
    runtime_zero = {
        "application_calls": 0,
        "evaluable_case_rows": 0,
        "provider_evidence_rows": 0,
        "provider_processing_events": 0,
        "retained_rows": 0,
        "runtime_rows": 0,
        "wire_attempts": 0,
    }
    require_equal(
        manifest["results"],
        {
            "adapter_contract_sha256": receipt["artifact_sha256"]["adapter_contract"],
            "authority_bundle_kat_sha256": sha256_value(authority_kat_instance()),
            "authority_receipt_schema_sha256": receipt["artifact_sha256"]["authority_receipt_schema"],
            **runtime_zero,
            "observation_sha256": receipt["artifact_sha256"]["observation"],
            "source_sha256": EXPECTED_SOURCE_SHA256,
            "stop_receipt_kat_sha256": sha256_value(stop_kat_instance(authority_kat_instance())),
            "stop_receipt_schema_sha256": receipt["artifact_sha256"]["stop_receipt_schema"],
        },
        "E_MANIFEST_RESULTS",
        "manifest results",
    )
    require_equal(
        manifest["test_oracle"],
        {
            "adapters": 9,
            "authority_artifacts": 5,
            "cases": 34,
            "client_conformance_double_rows": 420,
            "directed_negative_tests": negative_count,
            "managed_cases": 16,
            "managed_service_fault_proxy_rows": 210,
            "official_source_claims": 10,
            "planned_rows": 1020,
            "repetitions_per_case": 30,
            "schema_documents": 2,
            "self_hosted_adversarial_lab_rows": 390,
            "self_hosted_cases": 18,
            "stop_control_interfaces": 5,
            "tracks": 2,
        },
        "E_MANIFEST_ORACLE",
        "manifest test oracle",
    )
    require_equal(manifest["tracks"], receipt["track_results"], "E_MANIFEST_TRACKS", "manifest tracks")


def render_result_tsv(receipt: dict[str, Any], negative_count: int) -> str:
    fields: tuple[tuple[str, Any], ...] = (
        ("schema", receipt["schema"]),
        ("status", receipt["status"]),
        ("decision", receipt["decision"]),
        ("date", receipt["date"]),
        ("baseline_commit", receipt["baseline_commit"]),
        ("adapter_contract_sha256", receipt["artifact_sha256"]["adapter_contract"]),
        ("authority_receipt_schema_sha256", receipt["artifact_sha256"]["authority_receipt_schema"]),
        ("stop_receipt_schema_sha256", receipt["artifact_sha256"]["stop_receipt_schema"]),
        ("observation_sha256", receipt["artifact_sha256"]["observation"]),
        ("tracks", receipt["planned_counts"]["tracks"]),
        ("managed_cases", receipt["planned_counts"]["managed_cases"]),
        ("self_hosted_cases", receipt["planned_counts"]["self_hosted_cases"]),
        ("planned_rows", receipt["planned_counts"]["planned_rows"]),
        ("client_conformance_double_rows", receipt["planned_counts"]["client_conformance_double_rows"]),
        ("managed_service_fault_proxy_rows", receipt["planned_counts"]["managed_service_fault_proxy_rows"]),
        ("self_hosted_adversarial_lab_rows", receipt["planned_counts"]["self_hosted_adversarial_lab_rows"]),
        ("start_logic", receipt["authority_model"]["start_logic"]),
        ("stop_logic", receipt["authority_model"]["stop_logic"]),
        ("capability", receipt["authority_model"]["capability"]),
        ("contract_closure", receipt["data_quality"]["contract_closure"]),
        ("schema_closure", receipt["data_quality"]["schema_closure"]),
        ("synthetic_observation", receipt["data_quality"]["synthetic_observation"]),
        ("execution_evidence", receipt["data_quality"]["execution_evidence"]),
        ("experiment_executed", receipt["boundary"]["experiment_executed"]),
        ("provider_called", receipt["boundary"]["provider_called"]),
        ("credentials_accessed", receipt["boundary"]["credentials_accessed"]),
        ("runner_implemented", receipt["boundary"]["runner_implemented"]),
        ("adapter_implemented", receipt["boundary"]["adapter_implemented"]),
        ("execution_capability_emitted", receipt["boundary"]["execution_capability_emitted"]),
        ("stop_capability_emitted", receipt["boundary"]["stop_capability_emitted"]),
        ("receipt_is_execution_authority", receipt["boundary"]["receipt_is_execution_authority"]),
        ("receipt_is_output_permit", receipt["boundary"]["receipt_is_output_permit"]),
        ("side_effects_unlocked", receipt["boundary"]["side_effects_unlocked"]),
        ("managed_track_result", receipt["track_results"][MANAGED_TRACK]),
        ("self_hosted_track_result", receipt["track_results"][SELF_HOSTED_TRACK]),
        ("next_unit", receipt["next_unit"]),
        ("schema_documents_validated", 2),
        ("authority_bundle_kat_sha256", sha256_value(authority_kat_instance())),
        ("stop_receipt_kat_sha256", sha256_value(stop_kat_instance(authority_kat_instance()))),
        ("directed_negative_tests", negative_count),
        ("source_ast_purity", "PASS"),
        ("predecessor_artifacts_validated", len(PREDECESSOR_PATHS)),
    )

    def scalar(value: Any) -> str:
        if value is True:
            return "true"
        if value is False:
            return "false"
        if value is None:
            return "null"
        return str(value)

    return "".join(f"{label}\t{scalar(value)}\n" for label, value in fields)


def evaluate(root: Path, *, self_test: bool) -> tuple[str, int]:
    root = root.resolve()
    authority_schema, authority_raw = load_canonical(root / AUTHORITY_SCHEMA_PATH, "authority schema")
    adapter_contract, adapter_raw = load_canonical(root / ADAPTER_CONTRACT_PATH, "adapter contract")
    stop_schema, stop_raw = load_canonical(root / STOP_SCHEMA_PATH, "stop schema")
    observation, observation_raw = load_canonical(root / SYNTHETIC_PATH, "synthetic observation")
    manifest, manifest_raw = load_canonical(root / MANIFEST_PATH, "manifest")
    del manifest_raw

    validate_predecessor_artifacts(root)
    require(sha256_bytes(adapter_raw) == EXPECTED_CONTRACT_SHA256, "E_CONTRACT_HASH", "adapter contract byte hash drift")
    require(sha256_bytes(authority_raw) == EXPECTED_AUTHORITY_SCHEMA_SHA256, "E_AUTHORITY_SCHEMA_HASH", "authority schema byte hash drift")
    require(sha256_bytes(stop_raw) == EXPECTED_STOP_SCHEMA_SHA256, "E_STOP_SCHEMA_HASH", "stop schema byte hash drift")
    require(sha256_bytes(observation_raw) == EXPECTED_SYNTHETIC_SHA256, "E_OBSERVATION_HASH", "synthetic observation byte hash drift")
    module, source_text = load_source_module(root / SOURCE_PATH)
    require(sha256_bytes(source_text.encode("utf-8")) == EXPECTED_SOURCE_SHA256, "E_SOURCE_HASH", "source byte hash drift")
    required_api = (
        "validate_contract", "validate_authority_schema", "validate_stop_schema",
        "validate_observation", "build_validation_receipt", "render_tsv", "self_test",
    )
    for name in required_api:
        require(callable(getattr(module, name, None)), "E_SOURCE_API", f"source API missing {name}")
    receipt = validate_contract_semantics(
        adapter_contract, authority_schema, stop_schema, observation
    )
    try:
        source_receipt = module.build_validation_receipt(
            adapter_contract, authority_schema, stop_schema, observation
        )
        source_self_test_receipt = module.self_test(
            adapter_contract, authority_schema, stop_schema, observation
        )
    except Exception as exc:
        fail("E_SOURCE_VALIDATE", f"source positive validation failed: {exc}")
    require_equal(source_receipt, receipt, "E_SOURCE_RECEIPT", "source validation receipt")
    require_equal(source_self_test_receipt, receipt, "E_SOURCE_SELF_TEST", "source self-test receipt")
    negative_count = run_directed_negative_tests(
        adapter_contract, authority_schema, stop_schema, observation, module
    )
    rendered = render_result_tsv(receipt, negative_count)
    source_rendered = module.render_tsv(source_receipt)
    require(
        rendered.startswith(source_rendered),
        "E_SOURCE_TSV",
        "checker result does not preserve the exact 36-line source TSV prefix",
    )
    try:
        expected_raw = (root / EXPECTED_PATH).read_bytes()
    except OSError as exc:
        fail("E_EXPECTED_LOAD", f"cannot read expected TSV: {exc}")
    require(expected_raw == rendered.encode("utf-8"), "E_EXPECTED_TSV", "expected TSV drift")
    validate_manifest(root, manifest, receipt, negative_count)
    if self_test:
        repeated = validate_contract_semantics(
            copy.deepcopy(adapter_contract), copy.deepcopy(authority_schema),
            copy.deepcopy(stop_schema), copy.deepcopy(observation),
        )
        require_equal(repeated, receipt, "E_SELF_TEST_DETERMINISM", "repeated receipt")
        require(render_result_tsv(repeated, negative_count) == rendered, "E_SELF_TEST_DETERMINISM", "repeated TSV drift")
    return rendered, negative_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        rendered, _negative_count = evaluate(args.root, self_test=args.self_test)
    except PackError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
