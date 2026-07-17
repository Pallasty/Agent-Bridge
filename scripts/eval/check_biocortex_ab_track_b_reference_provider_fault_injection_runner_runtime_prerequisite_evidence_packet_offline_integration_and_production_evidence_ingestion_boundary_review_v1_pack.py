#!/usr/bin/env python3
"""Independent checker for the offline evidence-packet integration boundary."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, Callable, Mapping


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MIN_JSON_INTEGER = -(2**63)
MAX_JSON_INTEGER = 2**63 - 1

SUCCESSOR_MODULE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_packet_offline_integration_and_production_"
    "evidence_ingestion_boundary_review_v1.py"
)
BOUNDARY_FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_"
    "evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
)
EXPECTED_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_"
    "evidence_ingestion_boundary_review_v1_pack.expected.v0.tsv"
)
PREDECESSOR_MODULE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1.py"
)
PREDECESSOR_CHECKER_REL = (
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1_"
    "pack.py"
)
PREDECESSOR_PACK_FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_runtime_prerequisite_evidence_packet_schemas_and_offline_validator_"
    "doubles_v1_pack_synthetic_v0.json"
)
PREDECESSOR_PACK_EXPECTED_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_runtime_prerequisite_evidence_packet_schemas_and_offline_validator_"
    "doubles_v1_pack.expected.v0.tsv"
)
PREDECESSOR_PACK_MANIFEST_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_runtime_prerequisite_evidence_packet_schemas_and_offline_validator_"
    "doubles_v1_pack_v0.json"
)
PREDECESSOR_REPORT_REL = (
    "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-"
    "injection-runner-runtime-prerequisite-evidence-packet-schemas-and-offline-"
    "validator-doubles-v1-pack.md"
)
PREDECESSOR_GATE_REL = (
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-"
    "runtime-prerequisite-evidence-packet-schemas-and-offline-validator-doubles-v1-"
    "pack.sh"
)
PREREG_MANIFEST_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_"
    "v1_pack_v0.json"
)
PREREG_FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_"
    "v1_pack_synthetic_v0.json"
)
EVIDENCE_SCHEMA_REL = (
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-runtime-prerequisite-evidence-packet-schema-v1.json"
)
OWNER_SCHEMA_REL = (
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-owner-decision-packet-schema-v1.json"
)

PREDECESSOR_RAW_SHA256 = {
    PREDECESSOR_MODULE_REL: "29a4b67049429c09981f1742f072a3fe382f381259fa238b69041b3d46939351",
    PREDECESSOR_CHECKER_REL: "d1f3f93a8808cce859415282fc757ef2a11a64fde165f7c37247437c8ea5cee7",
    PREDECESSOR_PACK_FIXTURE_REL: "236839e4a8e831a84ef11c089cbd624152ddb456e583c2c414ece6c5ebb09f97",
    PREDECESSOR_PACK_EXPECTED_REL: "24317b383b71933f206331f5629e1e6e0ea09a8e0ba8372ee6fb2b40a64c4210",
    PREDECESSOR_PACK_MANIFEST_REL: "c5d448a121b58549a62e20ec7b241386ad73c9685ae9a981223a591555e2bd47",
    PREDECESSOR_REPORT_REL: "e431866b9545cade47aeb9b94f75638bb22dbd43b2c01c9c672acaff3e3de593",
    PREDECESSOR_GATE_REL: "df47afdefdf04bf6e82f29a7b867543edfb511d3d124a095a2e998eb8c72cbe0",
    PREREG_MANIFEST_REL: "caf420dd4f4d2b310d80bd56ab287f6ef527256c0126a48106438f6a344e6498",
    PREREG_FIXTURE_REL: "156b9a0357f1d5773fdd39be25d832e1d9e2e1df0d766b1947bbcc9cee118db3",
    EVIDENCE_SCHEMA_REL: "121c66331f159539722acb8f173696811487d8b76b9da07ab9d83340e28277d3",
    OWNER_SCHEMA_REL: "7845de2ac7d1f069fd550f5625a1593c0a093563acbe1be1855bf7df0f3d4436",
}
PREDECESSOR_CANONICAL_SHA256 = {
    PREREG_MANIFEST_REL: "59092d560b7df77bcb51d56a4d8974e345f28dfcafeaa7b765f24f27875818c4",
    PREREG_FIXTURE_REL: "279be92874e22e236d6c3db29e72c4602b33bd7fbef6f19c5c4b3608cfbf4d90",
    EVIDENCE_SCHEMA_REL: "a8b66deefe134afdb17e624bc821aba90c9d5a2490433f6a65276a6bfa63eaac",
    OWNER_SCHEMA_REL: "99f2737282f2df568792ced2f2e16820f74eb2820bcbe240eaa97c03cc197086",
    PREDECESSOR_PACK_FIXTURE_REL: "236839e4a8e831a84ef11c089cbd624152ddb456e583c2c414ece6c5ebb09f97",
    PREDECESSOR_PACK_MANIFEST_REL: "2eed1d7d33027a7a41bc3ced20038dabf3ae1b83e0cc94347b65822fca8e792c",
}
BOUNDARY_FIXTURE_SHA256 = "3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6"
PREDECESSOR_RECEIPT_SHA256 = "c6ea1a4872acacf1faff3695598d66e1cb0096f6574239199128225dab80e3c4"
SYNTHETIC_PACKET_SET_SHA256 = "56e9343e7e31e8a80d1a56f7ab34fc11e15412d97620c031a06f740ae29ea460"
CASE_RESULTS_SHA256 = "8852dc9a04a828e7756f73e8f65c7c39ef72ed2c046f2a8c0b8cdd27e598df58"
REQUEST_ID_SHA256 = "9a812f63f8b6fe4dd1b7a9e67e037b798e1da46e7be65377774e12d5ec6a2b45"
NONCLAIMS_SHA256 = "6123bcbfdba739acd61ea264c625b9f2545081701774a8c8b3b3a6f7b08f5b4a"
CONTENT_SHA256 = "7d48eb96d1a87894698d396efba848f90da8076cc3271bd9ac8c5250b0c722fa"

TRACKS = ("MANAGED_SPANNER_CLOUD_KMS", "SELF_HOSTED_ETCD_OPENBAO")
DOWNSTREAM_GATES = (
    "CONDITION_OUTPUT_GATE",
    "OUTPUT_PERMIT_GATE",
    "SCIENTIFIC_CLAIM_GATE",
    "APPLICATION_CLAIM_GATE",
)
TRUST_DOMAINS = (
    "AB_TRACK_B_RUNTIME_PREREQUISITE_SYNTHETIC_PACKET_SET_V1",
    "AB_TRACK_B_RUNTIME_PREREQUISITE_PRODUCTION_EVIDENCE_ENVELOPE_SIGNATURE_V1",
    "AB_TRACK_B_RUNTIME_PREREQUISITE_PRODUCTION_REVIEW_SUBJECT_SET_V1",
    "AB_TRACK_B_RUNTIME_PREREQUISITE_PRODUCTION_OWNER_HANDOFF_SET_V1",
    "AB_TRACK_B_RUNTIME_PREREQUISITE_PRODUCTION_OWNER_DECISION_SIGNATURE_V1",
)
CONTROL_IDS = (
    "FRAME_AND_PARSE", "SYNTHETIC_PRODUCTION_MODE_SEPARATION",
    "BOOTSTRAP_TRUST_AUTHENTICATION", "SIGNER_ROLE_SCOPE_AUTHORIZATION",
    "TRACK_SUBJECT_BINDING", "QUARANTINE_CUSTODY", "SEMANTIC_VALIDATION",
    "TRUSTED_TIME_FRESHNESS", "DURABLE_REPLAY_CAS",
    "VALIDATION_RECEIPT_BINDING", "INDEPENDENT_REVIEW_BINDING",
    "OWNER_HANDOFF_SET", "OWNER_IDENTITY_DECISION", "DOWNSTREAM_GATE_SEPARATION",
)
OWNER_HANDOFF_IDS = (
    "ALL_FIFTEEN_PRODUCTION_VALIDATED", "PACKET15_BINDS_ORDERED_ONE_TO_FOURTEEN",
    "OWNER_SET_BINDS_ORDERED_ONE_TO_FIFTEEN", "SAME_VALIDATED_SET_HASH",
    "TRUSTED_FINAL_VALIDATION_TIME", "OWNER_WINDOW_LESS_THAN_1800_SECONDS",
    "EFFECTIVE_DEADLINE_IS_MINIMUM_EXPIRY", "DECISION_TIME_RECHECKS_PASS",
    "OWNER_IDENTITY_AND_ROLE_AUTHENTICATED", "SEPARATE_POSITIVE_OWNER_SCHEMA_REQUIRED",
)
FRESHNESS_IDS = (
    "EXACT_BINDING_ONLY", "PROVIDER_IDENTITY_MAX_86400",
    "CREDENTIAL_LIFECYCLE_MAX_3600", "RESOURCE_BUDGET_MAX_86400",
    "TRUSTED_TIME_MAX_300", "SAFETY_STOP_DRILL_MAX_604800",
    "RETENTION_CLEANUP_MAX_604800", "OWNER_HANDOFF_MAX_1800",
)
NONCLAIM_FIELDS = {
    "application_claim_authorized", "condition_output_authorized", "credentials_accessed",
    "deployment_authorized", "evidence_receipt_accepted", "experiment_row_created",
    "independent_review_approved", "output_permit_defined", "owner_decision_recorded",
    "owner_handoff_ready", "owner_identity_bound", "paid_resource_provisioned",
    "positive_owner_decision_representable", "production_authenticator_implemented",
    "production_authority_verifier_implemented", "production_custody_record_committed",
    "production_custody_store_bound", "production_evidence_packet_accepted",
    "production_evidence_set_complete", "production_evidence_source_authenticated",
    "production_freshness_proved", "production_ingestion_endpoint_implemented",
    "production_ingestion_pipeline_implemented", "production_managed_adapter_implemented",
    "production_packet_schema_defined", "production_replay_ledger_bound",
    "production_replay_reservation_committed", "production_schema_validated",
    "production_self_hosted_adapter_implemented", "production_signature_verified",
    "production_stop_control_implemented", "production_subject_binding_validated",
    "production_track_binding_validated", "production_trust_bootstrap_bound",
    "production_trusted_time_bound", "production_validator_implemented", "provider_called",
    "provider_endpoint_bound", "real_evidence_collected", "real_evidence_ingestion_attempted",
    "real_runner_launched", "runtime_admission_granted", "runtime_admission_ready",
    "runtime_authority", "runtime_evidence_accepted", "runtime_prerequisite_satisfied",
    "runtime_row_created", "scientific_claim_authorized", "secret_material_present",
    "side_effects_unlocked", "trusted_time_accessed", "wire_attempted",
}


class CheckError(ValueError):
    """Independent fail-closed checker error."""


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise CheckError(f"{code}: {message}")


def exact_keys(value: Mapping[str, Any], expected: set[str], code: str) -> None:
    require(type(value) is dict and set(value) == expected, code, "closed-world key set drift")


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                   allow_nan=False, separators=(",", ": "))
        + "\n"
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def without_key(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    require(key in result, "E_HASH_FIELD", key)
    del result[key]
    return result


def is_sha256(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def safe_path(relative: str) -> Path:
    parsed = PurePosixPath(relative)
    require(not parsed.is_absolute() and ".." not in parsed.parts and str(parsed) == relative,
            "E_PATH", relative)
    cursor = ROOT
    for component in parsed.parts:
        cursor = cursor / component
        require(not cursor.is_symlink(), "E_PATH_SYMLINK", relative)
    path = cursor
    require(path.is_file() and not path.is_symlink(), "E_FILE", relative)
    resolved = path.resolve()
    require(ROOT == resolved or ROOT in resolved.parents, "E_PATH_ESCAPE", relative)
    return path


def read_bytes(relative: str) -> bytes:
    raw = safe_path(relative).read_bytes()
    require(len(raw) <= MAX_DOCUMENT_BYTES, "E_SIZE", relative)
    return raw


def raw_sha256(relative: str) -> str:
    return hashlib.sha256(read_bytes(relative)).hexdigest()


def _duplicate_safe_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "E_DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def _bounded_integer(token: str) -> int:
    value = int(token, 10)
    require(MIN_JSON_INTEGER <= value <= MAX_JSON_INTEGER, "E_JSON_INTEGER_OVERFLOW", token)
    return value


def _reject_float(token: str) -> float:
    raise CheckError(f"E_JSON_FLOAT: {token}")


def _reject_constant(token: str) -> None:
    raise CheckError(f"E_JSON_NONFINITE: {token}")


def parse_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    require(not raw.startswith(b"\xef\xbb\xbf"), "E_JSON_BOM", label)
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(text, object_pairs_hook=_duplicate_safe_object,
                           parse_int=_bounded_integer, parse_float=_reject_float,
                           parse_constant=_reject_constant)
    except UnicodeDecodeError as error:
        raise CheckError(f"E_UTF8: {label}") from error
    require(type(value) is dict, "E_JSON_ROOT", label)
    return value


def read_json(relative: str) -> dict[str, Any]:
    return parse_json_bytes(read_bytes(relative), relative)


def read_text(relative: str) -> str:
    try:
        return read_bytes(relative).decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise CheckError(f"E_UTF8: {relative}") from error


def check_decoder_guards() -> int:
    probes = (
        b'{"a":1,"a":2}', b'{"value":NaN}',
        b'{"value":9223372036854775808}', b'{"value":1.25}',
    )
    for index, raw in enumerate(probes):
        try:
            parse_json_bytes(raw, f"guard-{index}")
        except CheckError:
            continue
        raise CheckError(f"E_JSON_GUARD_PROBE: {index}")
    return len(probes)


def load_module(relative: str, name: str) -> ModuleType:
    path = safe_path(relative).resolve()
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "E_MODULE_LOAD", name)
    require(spec.origin is not None and Path(spec.origin).resolve() == path, "E_MODULE_ORIGIN", name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    require(Path(module.__file__).resolve() == path, "E_MODULE_PATH", name)
    return module


def check_successor_source_purity() -> None:
    text = read_text(SUCCESSOR_MODULE_REL)
    tree = ast.parse(text, filename=SUCCESSOR_MODULE_REL)
    predecessor_name = Path(PREDECESSOR_MODULE_REL).stem
    allowed_imports = {"__future__", "copy", "hashlib", "json", "typing"}
    forbidden_calls = {"__import__", "compile", "eval", "exec", "input", "open"}
    forbidden_attrs = {
        "read", "read_bytes", "read_text", "write", "write_bytes", "write_text",
        "unlink", "mkdir", "makedirs", "getenv", "environ", "now", "utcnow",
        "today", "time", "sleep", "run", "Popen", "connect", "request", "urlopen",
        "import_module", "urandom", "token_bytes", "token_hex", "randbytes",
    }
    target_methods: set[str] | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".", 1)[0] in allowed_imports, "E_AST_IMPORT", alias.name)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name == predecessor_name:
                require([(a.name, a.asname) for a in node.names]
                        == [("EvidencePacketReviewError", None),
                            ("RuntimePrerequisiteEvidencePacketSchemaReviewer", None)],
                        "E_AST_PREDECESSOR_IMPORT", "exact import")
            else:
                require(module_name.split(".", 1)[0] in allowed_imports,
                        "E_AST_IMPORT", module_name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(node.func.id not in forbidden_calls, "E_AST_CALL", node.func.id)
            elif isinstance(node.func, ast.Attribute):
                require(node.func.attr not in forbidden_attrs, "E_AST_CALL", node.func.attr)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            raise CheckError("E_AST_MUTABLE_SCOPE: global/nonlocal")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                lower = node.name.lower()
                require("ingest" not in lower and "accept" not in lower,
                        "E_PUBLIC_PRODUCTION_API", node.name)
        elif isinstance(node, ast.ClassDef) and node.name == (
            "RuntimePrerequisiteEvidencePacketOfflineIntegrationBoundaryReviewer"
        ):
            target_methods = {
                item.name for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not item.name.startswith("_")
            }
    require(target_methods == {"known_answer_aggregate_request", "validate_aggregate_request", "review"},
            "E_PUBLIC_API", str(target_methods))


def verify_predecessor_artifacts() -> tuple[dict[str, Any], ...]:
    for relative, expected in PREDECESSOR_RAW_SHA256.items():
        require(raw_sha256(relative) == expected, "E_PREDECESSOR_RAW_HASH", relative)
    documents = {
        PREREG_MANIFEST_REL: read_json(PREREG_MANIFEST_REL),
        PREREG_FIXTURE_REL: read_json(PREREG_FIXTURE_REL),
        EVIDENCE_SCHEMA_REL: read_json(EVIDENCE_SCHEMA_REL),
        OWNER_SCHEMA_REL: read_json(OWNER_SCHEMA_REL),
        PREDECESSOR_PACK_FIXTURE_REL: read_json(PREDECESSOR_PACK_FIXTURE_REL),
        PREDECESSOR_PACK_MANIFEST_REL: read_json(PREDECESSOR_PACK_MANIFEST_REL),
    }
    for relative, expected in PREDECESSOR_CANONICAL_SHA256.items():
        require(sha256_value(documents[relative]) == expected,
                "E_PREDECESSOR_CANONICAL_HASH", relative)
    pack_manifest = documents[PREDECESSOR_PACK_MANIFEST_REL]
    require(pack_manifest.get("logical_baseline_commit")
            == "8af4af0e5ceea8062b65ac06870cabf789567053", "E_PACK_MANIFEST", "baseline")
    require(pack_manifest.get("results", {}).get("content_sha256") == PREDECESSOR_RECEIPT_SHA256,
            "E_PACK_MANIFEST", "receipt")
    require(pack_manifest.get("results", {}).get("synthetic_packet_set_sha256")
            == SYNTHETIC_PACKET_SET_SHA256, "E_PACK_MANIFEST", "packet set")
    return (
        documents[PREREG_MANIFEST_REL], documents[PREREG_FIXTURE_REL],
        documents[EVIDENCE_SCHEMA_REL], documents[OWNER_SCHEMA_REL],
        documents[PREDECESSOR_PACK_FIXTURE_REL],
    )


def validate_boundary_fixture(fixture: dict[str, Any], predecessor_fixture: dict[str, Any],
                              *, enforce_hash: bool = True) -> None:
    if enforce_hash:
        require(raw_sha256(BOUNDARY_FIXTURE_REL) == BOUNDARY_FIXTURE_SHA256,
                "E_BOUNDARY_RAW_HASH", "fixture")
        require(sha256_value(fixture) == BOUNDARY_FIXTURE_SHA256,
                "E_BOUNDARY_CANONICAL_HASH", "fixture")
    exact_keys(fixture, {
        "date", "downstream_separate_gates", "expected", "freshness_requirements",
        "nonclaims", "owner_handoff_requirements", "predecessor",
        "production_ingestion_controls", "schema", "synthetic_only", "threat_cases",
        "tracks", "trust_domains",
    }, "E_BOUNDARY_KEYS")
    require(fixture["date"] == "2026-07-17" and fixture["synthetic_only"] is True,
            "E_BOUNDARY_IDENTITY", "date/mode")
    require(fixture["tracks"] == list(TRACKS), "E_BOUNDARY_TRACKS", "order")
    require(fixture["downstream_separate_gates"] == list(DOWNSTREAM_GATES),
            "E_BOUNDARY_GATES", "order")
    predecessor = fixture["predecessor"]
    exact_keys(predecessor, {
        "evidence_schema_canonical_json_sha256", "evidence_schema_file_bytes_sha256",
        "integration_commit", "owner_schema_canonical_json_sha256",
        "owner_schema_file_bytes_sha256", "receipt_content_sha256",
        "reviewer_file_bytes_sha256", "schema_fixture_canonical_json_sha256",
        "source_commit", "synthetic_packet_set_sha256",
    }, "E_BOUNDARY_PREDECESSOR_KEYS")
    require(predecessor == {
        "evidence_schema_canonical_json_sha256": PREDECESSOR_CANONICAL_SHA256[EVIDENCE_SCHEMA_REL],
        "evidence_schema_file_bytes_sha256": PREDECESSOR_RAW_SHA256[EVIDENCE_SCHEMA_REL],
        "integration_commit": "3d03193b645ded944b10a310633be8d6a2c1ab1b",
        "owner_schema_canonical_json_sha256": PREDECESSOR_CANONICAL_SHA256[OWNER_SCHEMA_REL],
        "owner_schema_file_bytes_sha256": PREDECESSOR_RAW_SHA256[OWNER_SCHEMA_REL],
        "receipt_content_sha256": PREDECESSOR_RECEIPT_SHA256,
        "reviewer_file_bytes_sha256": PREDECESSOR_RAW_SHA256[PREDECESSOR_MODULE_REL],
        "schema_fixture_canonical_json_sha256": PREDECESSOR_CANONICAL_SHA256[PREDECESSOR_PACK_FIXTURE_REL],
        "source_commit": "151c3294c92e79759401cf86e8f36263bbf17ade",
        "synthetic_packet_set_sha256": SYNTHETIC_PACKET_SET_SHA256,
    }, "E_BOUNDARY_PREDECESSOR", "exact binding")

    domains = fixture["trust_domains"]
    require(type(domains) is list and len(domains) == 5, "E_DOMAIN_COUNT", "five")
    require([row.get("domain_id") for row in domains] == list(TRUST_DOMAINS),
            "E_DOMAIN_ORDER", "ids")
    for index, row in enumerate(domains):
        exact_keys(row, {"cross_domain_substitution_allowed", "domain_id", "offline_usable",
                         "production_implemented", "purpose"}, "E_DOMAIN_KEYS")
        require(row["production_implemented"] is False
                and row["cross_domain_substitution_allowed"] is False
                and row["offline_usable"] is (index == 0), "E_DOMAIN_BOUNDARY", str(index))
        require(type(row["purpose"]) is str and row["purpose"], "E_DOMAIN_PURPOSE", str(index))

    controls = fixture["production_ingestion_controls"]
    require(type(controls) is list and len(controls) == 14, "E_CONTROL_COUNT", "fourteen")
    require([row.get("control_id") for row in controls] == list(CONTROL_IDS),
            "E_CONTROL_ORDER", "ids")
    failure_codes = set()
    for ordinal, row in enumerate(controls, start=1):
        exact_keys(row, {"control_id", "implemented", "mandatory_check", "primary_failure_code",
                         "required_future_artifact", "runtime_exercised", "satisfiable_by_offline",
                         "stage_ordinal"}, "E_CONTROL_KEYS")
        require(row["stage_ordinal"] == ordinal, "E_CONTROL_ORDINAL", str(ordinal))
        require(row["implemented"] is False and row["runtime_exercised"] is False
                and row["satisfiable_by_offline"] is False, "E_CONTROL_BOUNDARY", str(ordinal))
        for field in ("mandatory_check", "primary_failure_code", "required_future_artifact"):
            require(type(row[field]) is str and row[field], "E_CONTROL_TEXT", field)
        failure_codes.add(row["primary_failure_code"])

    threats = fixture["threat_cases"]
    require(type(threats) is list and len(threats) == 20, "E_THREAT_COUNT", "twenty")
    require([row.get("case_id") for row in threats] == [f"T{i:02d}" for i in range(1, 21)],
            "E_THREAT_ORDER", "ids")
    for row in threats:
        exact_keys(row, {"case_id", "expected_disposition", "expected_reason_code", "mutation",
                         "threat_class"}, "E_THREAT_KEYS")
        require(row["expected_disposition"] == "REJECTED_FAIL_CLOSED",
                "E_THREAT_DISPOSITION", row["case_id"])
        require(row["expected_reason_code"] in failure_codes, "E_THREAT_REASON", row["case_id"])
        require(type(row["mutation"]) is str and row["mutation"]
                and type(row["threat_class"]) is str and row["threat_class"],
                "E_THREAT_TEXT", row["case_id"])

    handoff = fixture["owner_handoff_requirements"]
    require(type(handoff) is list and len(handoff) == 10, "E_HANDOFF_COUNT", "ten")
    require([row.get("requirement_id") for row in handoff] == list(OWNER_HANDOFF_IDS),
            "E_HANDOFF_ORDER", "ids")
    for row in handoff:
        exact_keys(row, {"offline_substitution_allowed", "production_implemented", "requirement",
                         "requirement_id", "satisfied"}, "E_HANDOFF_KEYS")
        require(row["offline_substitution_allowed"] is False
                and row["production_implemented"] is False and row["satisfied"] is False,
                "E_HANDOFF_BOUNDARY", row["requirement_id"])
        require(type(row["requirement"]) is str and row["requirement"],
                "E_HANDOFF_TEXT", row["requirement_id"])

    freshness = fixture["freshness_requirements"]
    require(type(freshness) is list and len(freshness) == 8, "E_FRESHNESS_COUNT", "eight")
    require([row.get("freshness_id") for row in freshness] == list(FRESHNESS_IDS),
            "E_FRESHNESS_ORDER", "ids")
    max_ages = (None, 86400, 3600, 86400, 300, 604800, 604800, 1800)
    rechecks = (False, True, True, True, True, False, False, True)
    covered: list[str] = []
    for index, row in enumerate(freshness):
        exact_keys(row, {"additional_requirement", "decision_recheck_required", "freshness_id",
                         "max_age_seconds", "prerequisite_ids", "production_implemented",
                         "real_currentness_proved"}, "E_FRESHNESS_KEYS")
        require(row["max_age_seconds"] == max_ages[index]
                and row["decision_recheck_required"] is rechecks[index],
                "E_FRESHNESS_RULE", row["freshness_id"])
        require(row["production_implemented"] is False and row["real_currentness_proved"] is False,
                "E_FRESHNESS_BOUNDARY", row["freshness_id"])
        require(type(row["prerequisite_ids"]) is list and row["prerequisite_ids"],
                "E_FRESHNESS_PREREQUISITES", row["freshness_id"])
        covered.extend(row["prerequisite_ids"])
    plan_ids = [row["prerequisite_id"] for row in predecessor_fixture["prerequisite_evidence_plan"]]
    require(len(covered) == len(set(covered)) == 16 and set(covered) == set(plan_ids),
            "E_FRESHNESS_COVERAGE", "all prerequisites exactly once")

    nonclaims = fixture["nonclaims"]
    exact_keys(nonclaims, NONCLAIM_FIELDS, "E_NONCLAIM_KEYS")
    for field, value in nonclaims.items():
        if field == "side_effects_unlocked":
            require(value == "NONE", "E_NONCLAIM", field)
        else:
            require(value is False, "E_NONCLAIM", field)

    expected = fixture["expected"]
    require(expected == {
        "aggregate_case_result_count": 16, "aggregate_evidence_packet_count": 15,
        "downstream_gate_count": 4, "freshness_requirement_count": 8,
        "nonclaim_field_count": 52, "offline_double_conformant_count": 16,
        "owner_handoff_eligible": False, "owner_handoff_requirement_count": 10,
        "owner_packet_count": 1, "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_validated_evidence_items": 0, "real_evidence_items_present": 0,
        "runtime_prerequisites_satisfied": 0,
        "synthetic_packet_set_sha256": SYNTHETIC_PACKET_SET_SHA256,
        "threat_case_count": 20, "tracks_represented": 2, "trust_domain_count": 5,
        "valid_owner_state_reason_combination_count": 6,
    }, "E_EXPECTED", "exact boundary expectations")


def derive_packet_set(packet_ids: list[str]) -> str:
    require(len(packet_ids) == len(set(packet_ids)) == 15 and all(is_sha256(v) for v in packet_ids),
            "E_PACKET_SET", "ids")
    return sha256_value({
        "canonicalization": "AGENT_BRIDGE_CANONICAL_JSON_V1_SORTED_KEYS_INDENT_2_LF",
        "domain": "AB_TRACK_B_RUNTIME_PREREQUISITE_SYNTHETIC_PACKET_SET_V1",
        "ordered_packet_id_sha256": packet_ids,
    })


def derive_request_id(request: Mapping[str, Any]) -> str:
    return sha256_value({
        "domain": "AB_TRACK_B_RUNTIME_PREREQUISITE_SYNTHETIC_OFFLINE_AGGREGATE_REQUEST_V1",
        "request": without_key(request, "request_id_sha256"),
    })


def call_predecessor_public_api(module: ModuleType, documents: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    reviewer = module.RuntimePrerequisiteEvidencePacketSchemaReviewer()
    args = tuple(copy.deepcopy(item) for item in documents)
    suite = reviewer.known_answer_packet_suite(*args)
    exact_keys(suite, {"evidence_packets", "owner_packet"}, "E_PREDECESSOR_SUITE")
    require(type(suite["evidence_packets"]) is list and len(suite["evidence_packets"]) == 15,
            "E_PREDECESSOR_SUITE", "evidence count")
    results = []
    for index, packet in enumerate(suite["evidence_packets"]):
        results.append(reviewer.validate_evidence_packet_double(*args, index, copy.deepcopy(packet)))
    results.append(reviewer.validate_owner_packet_double(*args, copy.deepcopy(suite["owner_packet"])))
    receipt = reviewer.review(*args)
    require(receipt["case_results"] == results, "E_PREDECESSOR_RESULTS", "public API drift")
    require(receipt["content_sha256"] == PREDECESSOR_RECEIPT_SHA256,
            "E_PREDECESSOR_RECEIPT", "content")
    require(receipt["synthetic_packet_set_sha256"] == SYNTHETIC_PACKET_SET_SHA256,
            "E_PREDECESSOR_RECEIPT", "set")
    require(module.render_tsv(receipt) == read_text(PREDECESSOR_PACK_EXPECTED_REL),
            "E_PREDECESSOR_TSV", "oracle")
    return suite, results, receipt


def validate_request(request: dict[str, Any], suite: dict[str, Any],
                     predecessor_fixture: dict[str, Any], schema_fixture: dict[str, Any]) -> list[str]:
    exact_keys(request, {"evidence_packets", "mode", "owner_packet", "request_id_sha256",
                         "schema", "schema_version", "synthetic_context_sha256"},
               "E_REQUEST_KEYS")
    require(request["mode"] == "SYNTHETIC_FIXED_KAT_ONLY"
            and type(request["schema_version"]) is int and request["schema_version"] == 1,
            "E_REQUEST_IDENTITY", "mode/version")
    require(request["request_id_sha256"] == derive_request_id(request) == REQUEST_ID_SHA256,
            "E_REQUEST_ID", "domain-separated content id")
    require(request["synthetic_context_sha256"] == sha256_value(schema_fixture["synthetic_context"]),
            "E_REQUEST_CONTEXT", "context")
    require(request["evidence_packets"] == suite["evidence_packets"]
            and request["owner_packet"] == suite["owner_packet"],
            "E_REQUEST_KAT", "exact predecessor suite")
    packets = request["evidence_packets"]
    plan = predecessor_fixture["prerequisite_evidence_plan"]
    require([p["prerequisite_id"] for p in packets]
            == [row["prerequisite_id"] for row in plan[:15]], "E_REQUEST_ORDER", "plan")
    packet_ids = [p["packet_id_sha256"] for p in packets]
    require(len(packet_ids) == len(set(packet_ids)) == 15, "E_REQUEST_UNIQUE", "packet ids")
    for index, packet in enumerate(packets):
        require(packet["packet_id_sha256"] == sha256_value(without_key(packet, "packet_id_sha256")),
                "E_PACKET_CONTENT_ID", str(index))
        require(packet["packet_kind"] == "SYNTHETIC_VALIDATOR_DOUBLE",
                "E_PACKET_KIND", str(index))
    review_payload = packets[14]["payload"]
    require(review_payload["ordered_prerequisite_packet_id_sha256"] == packet_ids[:14],
            "E_PACKET15_ORDER", "1-14")
    expected_review_set = sha256_value({
        "canonicalization": "AGENT_BRIDGE_CANONICAL_JSON_V1_SORTED_KEYS_INDENT_2_LF",
        "domain": "AB_TRACK_B_RUNTIME_PREREQUISITE_SYNTHETIC_PACKET_SET_V1",
        "ordered_packet_id_sha256": packet_ids[:14],
    })
    require(review_payload["evidence_set_sha256"] == expected_review_set,
            "E_PACKET15_SET", "ordered 1-14")
    owner = request["owner_packet"]
    require(owner["packet_id_sha256"] == sha256_value(without_key(owner, "packet_id_sha256")),
            "E_OWNER_PACKET_ID", "content")
    require(owner["decision_state"] == "PENDING_PREREQUISITE_EVIDENCE"
            and owner["decision_reason"] == "WAITING_FOR_ALL_EVIDENCE"
            and owner["decision_recorded"] is False
            and owner["positive_decision_representable"] is False,
            "E_OWNER_PENDING", "state")
    require(owner["evidence_set_binding"]["evidence_set_sha256"] == "NONE"
            and owner["owner_identity_bound"] is False, "E_OWNER_BOUNDARY", "unbound")
    require(derive_packet_set(packet_ids) == SYNTHETIC_PACKET_SET_SHA256,
            "E_REQUEST_SET", "frozen")
    return packet_ids


def validate_case_results(case_results: list[dict[str, Any]], expected_results: list[dict[str, Any]],
                          packet_ids: list[str], owner_id: str,
                          predecessor_fixture: dict[str, Any]) -> None:
    require(type(case_results) is list and len(case_results) == 16, "E_CASE_COUNT", "sixteen")
    require(case_results == expected_results, "E_CASE_RESULTS", "public validator results")
    expected_ids = [row["prerequisite_id"] for row in predecessor_fixture["prerequisite_evidence_plan"]]
    for index, result in enumerate(case_results):
        exact_keys(result, {"offline_double_conformant", "packet_id_sha256", "packet_schema_id",
                            "prerequisite_disposition", "prerequisite_id", "primary_reason",
                            "real_evidence_items", "runtime_evidence_disposition",
                            "schema_conformant", "schema_disposition"}, "E_CASE_KEYS")
        require(result["prerequisite_id"] == expected_ids[index], "E_CASE_ORDER", str(index))
        require(result["packet_id_sha256"] == (packet_ids[index] if index < 15 else owner_id),
                "E_CASE_PACKET", str(index))
        require(result["schema_conformant"] is True
                and result["offline_double_conformant"] is True
                and result["real_evidence_items"] == 0
                and result["runtime_evidence_disposition"] == "NOT_EVALUATED_OUT_OF_SCOPE"
                and result["prerequisite_disposition"] == "PENDING_NOT_COLLECTED",
                "E_CASE_BOUNDARY", str(index))
    require(sha256_value(case_results) == CASE_RESULTS_SHA256, "E_CASE_HASH", "frozen")


RECEIPT_KEYS = {
    "aggregate_case_result_count", "aggregate_request_id_sha256", "all_nonclaims_explicit",
    "boundary_fixture_sha256", "case_results", "case_results_sha256", "content_sha256",
    "date", "decision", "dependency_topology_conformant", "downstream_gates_authorized",
    "downstream_separate_gate_count", "evidence_packet_count",
    "freshness_arithmetic_conformant_count", "freshness_requirement_count", "mode",
    "next_unit", "nonclaim_field_count", "nonclaims_sha256", "offline_double_conformant_count",
    "ordered_packet_id_sha256", "owner_decision_recorded", "owner_handoff_eligible",
    "owner_handoff_requirement_count", "owner_handoff_set_sha256", "owner_identity_bound",
    "owner_packet_count", "positive_decision_representable",
    "predecessor_receipt_content_sha256", "production_evidence_ingestion_implemented",
    "production_ingestion_control_count", "production_ingestion_controls_implemented",
    "production_review_subject_set_sha256", "production_validated_evidence_items",
    "real_currentness_proved", "real_evidence_items_present", "runtime_admission_granted",
    "runtime_admission_ready", "runtime_authority", "runtime_evidence_accepted",
    "runtime_prerequisites_satisfied", "schema", "side_effects_unlocked", "status",
    "synthetic_packet_set_sha256", "threat_case_count", "track_separation_conformant",
    "tracks_represented", "trust_domain_count", "valid_owner_state_reason_combination_count",
}


def validate_receipt(receipt: dict[str, Any], module: ModuleType, request: dict[str, Any],
                     expected_results: list[dict[str, Any]], predecessor_fixture: dict[str, Any],
                     boundary_fixture: dict[str, Any]) -> str:
    exact_keys(receipt, RECEIPT_KEYS, "E_RECEIPT_KEYS")
    packet_ids = [p["packet_id_sha256"] for p in request["evidence_packets"]]
    validate_case_results(receipt["case_results"], expected_results, packet_ids,
                          request["owner_packet"]["packet_id_sha256"], predecessor_fixture)
    exact_scalars = {
        "schema": module.RECEIPT_SCHEMA, "status": module.STATUS, "decision": module.DECISION,
        "date": "2026-07-17", "mode": "SYNTHETIC_FIXED_KAT_ONLY",
        "next_unit": module.NEXT_UNIT, "tracks_represented": 2, "evidence_packet_count": 15,
        "owner_packet_count": 1, "aggregate_case_result_count": 16,
        "offline_double_conformant_count": 16, "freshness_arithmetic_conformant_count": 15,
        "dependency_topology_conformant": True, "track_separation_conformant": True,
        "synthetic_packet_set_sha256": SYNTHETIC_PACKET_SET_SHA256,
        "case_results_sha256": CASE_RESULTS_SHA256,
        "aggregate_request_id_sha256": REQUEST_ID_SHA256,
        "predecessor_receipt_content_sha256": PREDECESSOR_RECEIPT_SHA256,
        "boundary_fixture_sha256": BOUNDARY_FIXTURE_SHA256, "trust_domain_count": 5,
        "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0, "threat_case_count": 20,
        "freshness_requirement_count": 8, "owner_handoff_requirement_count": 10,
        "valid_owner_state_reason_combination_count": 6, "nonclaim_field_count": 52,
        "nonclaims_sha256": NONCLAIMS_SHA256, "all_nonclaims_explicit": True,
        "real_evidence_items_present": 0, "production_validated_evidence_items": 0,
        "runtime_evidence_accepted": 0, "runtime_prerequisites_satisfied": 0,
        "real_currentness_proved": False, "production_evidence_ingestion_implemented": False,
        "production_review_subject_set_sha256": "NONE", "owner_handoff_set_sha256": "NONE",
        "owner_handoff_eligible": False, "owner_identity_bound": False,
        "owner_decision_recorded": False, "positive_decision_representable": False,
        "runtime_admission_ready": False, "runtime_admission_granted": False,
        "runtime_authority": False, "downstream_separate_gate_count": 4,
        "downstream_gates_authorized": 0, "side_effects_unlocked": "NONE",
    }
    for field, expected in exact_scalars.items():
        require(receipt[field] == expected and type(receipt[field]) is type(expected),
                "E_RECEIPT_VALUE", field)
    require(receipt["ordered_packet_id_sha256"] == packet_ids, "E_RECEIPT_ORDER", "packet ids")
    require(receipt["case_results_sha256"] == sha256_value(receipt["case_results"]),
            "E_RECEIPT_HASH", "cases")
    require(receipt["nonclaims_sha256"] == sha256_value(boundary_fixture["nonclaims"]),
            "E_RECEIPT_HASH", "nonclaims")
    require(receipt["content_sha256"] == sha256_value(without_key(receipt, "content_sha256"))
            == CONTENT_SHA256, "E_RECEIPT_HASH", "content")
    expected_text = read_text(EXPECTED_REL)
    expected_field_order = tuple(
        line.split("\t", 1)[0] for line in expected_text.splitlines()
    )
    require(tuple(module.TSV_FIELDS) == expected_field_order,
            "E_TSV_FIELDS", "frozen field order")
    rendered = independent_render_tsv(receipt, tuple(module.TSV_FIELDS))
    require(module.render_tsv(receipt) == rendered, "E_TSV_RENDER", "module")
    require(rendered == expected_text, "E_TSV_EXPECTED", "oracle")
    return rendered


def independent_render_tsv(receipt: Mapping[str, Any], fields: tuple[str, ...]) -> str:
    require(set(fields) | {"case_results", "ordered_packet_id_sha256"} == RECEIPT_KEYS,
            "E_TSV_FIELDS", "exact receipt projection")
    lines = []
    for field in fields:
        value = receipt[field]
        require(type(value) in (str, int, bool), "E_TSV_SCALAR", field)
        rendered = "true" if value is True else "false" if value is False else str(value)
        require("\t" not in rendered and "\n" not in rendered, "E_TSV_INJECTION", field)
        lines.append(f"{field}\t{rendered}")
    return "\n".join(lines) + "\n"


def validate_owner_state_reason_matrix(
    module: ModuleType,
    documents: tuple[dict[str, Any], ...],
    boundary_fixture: dict[str, Any],
    request: dict[str, Any],
) -> int:
    """Exercise all six legal fail-closed owner KATs through the successor API."""

    combinations = (
        ("PENDING_PREREQUISITE_EVIDENCE", "WAITING_FOR_ALL_EVIDENCE"),
        ("PENDING_PREREQUISITE_EVIDENCE", "OWNER_DECISION_PENDING"),
        ("REJECTED_FAIL_CLOSED", "EVIDENCE_VALIDATION_FAILED"),
        ("REJECTED_FAIL_CLOSED", "EVIDENCE_FRESHNESS_FAILED"),
        ("REJECTED_FAIL_CLOSED", "EVIDENCE_BINDING_FAILED"),
        ("REJECTED_FAIL_CLOSED", "POSITIVE_DECISION_NOT_REPRESENTABLE"),
    )
    reviewer = module.RuntimePrerequisiteEvidencePacketOfflineIntegrationBoundaryReviewer()
    checked_at = documents[4]["synthetic_context"]["checked_at_utc"]
    observed_packet_ids: list[str] = []
    for state, reason in combinations:
        candidate = copy.deepcopy(request)
        owner = candidate["owner_packet"]
        owner["decision_state"] = state
        owner["decision_reason"] = reason
        binding = owner["evidence_set_binding"]
        if state == "PENDING_PREREQUISITE_EVIDENCE":
            binding["final_validation_state"] = "NOT_PERFORMED"
            binding["final_validation_at_utc"] = "NONE"
            expected_disposition = "PENDING_NOT_COLLECTED"
        else:
            binding["final_validation_state"] = "REJECTED_FAIL_CLOSED"
            binding["final_validation_at_utc"] = checked_at
            expected_disposition = "REJECTED_FAIL_CLOSED"
        owner["packet_id_sha256"] = sha256_value(without_key(owner, "packet_id_sha256"))
        candidate["request_id_sha256"] = derive_request_id(candidate)
        combination_receipt = reviewer.validate_aggregate_request(
            *copy.deepcopy(documents),
            copy.deepcopy(boundary_fixture),
            candidate,
        )
        owner_result = combination_receipt["case_results"][-1]
        require(
            owner_result["primary_reason"] == reason
            and owner_result["prerequisite_disposition"] == expected_disposition
            and owner_result["packet_id_sha256"] == owner["packet_id_sha256"],
            "E_OWNER_MATRIX_RESULT",
            f"{state}:{reason}",
        )
        require(
            combination_receipt["owner_decision_recorded"] is False
            and combination_receipt["owner_identity_bound"] is False
            and combination_receipt["runtime_admission_granted"] is False
            and combination_receipt["runtime_authority"] is False
            and combination_receipt["runtime_prerequisites_satisfied"] == 0,
            "E_OWNER_MATRIX_BOUNDARY",
            f"{state}:{reason}",
        )
        observed_packet_ids.append(owner["packet_id_sha256"])
    require(
        len(observed_packet_ids) == len(set(observed_packet_ids)) == 6,
        "E_OWNER_MATRIX_IDS",
        "content-derived owner KAT ids",
    )
    return len(combinations)


def expect_rejected(action: Callable[[], Any], label: str) -> None:
    try:
        action()
    except (CheckError, ValueError, TypeError, KeyError):
        return
    raise CheckError(f"E_MUTATION_ACCEPTED: {label}")


def mutate_scalar(value: Any) -> Any:
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is str:
        return "0" * 64 if is_sha256(value) else value + "_MUTATED"
    if value is None:
        return 0
    if type(value) is list:
        return list(reversed(value)) if len(value) > 1 else value + ["MUTATED"]
    if type(value) is dict:
        result = copy.deepcopy(value); result["extra"] = False; return result
    raise CheckError("E_MUTATOR_TYPE: unsupported")


def run_self_test(module: ModuleType, documents: tuple[dict[str, Any], ...],
                  boundary_fixture: dict[str, Any],
                  request: dict[str, Any], receipt: dict[str, Any],
                  expected_results: list[dict[str, Any]],
                  valid_owner_combinations: int) -> dict[str, int]:
    counts = {"json_guard_negatives": check_decoder_guards(),
              "fixture_semantic_negatives": 0, "aggregate_semantic_negatives": 0,
              "receipt_semantic_negatives": 0,
              "valid_owner_state_reason_combinations": valid_owner_combinations}
    predecessor_fixture = documents[1]
    reviewer = module.RuntimePrerequisiteEvidencePacketOfflineIntegrationBoundaryReviewer()

    fixture_mutators: list[tuple[str, Callable[[dict[str, Any]], None]]] = []
    for key in boundary_fixture:
        fixture_mutators.append((f"fixture-drop-{key}", lambda item, key=key: item.pop(key)))
    fixture_mutators.append(("fixture-extra", lambda item: item.__setitem__("extra", False)))
    for index in range(5):
        fixture_mutators.append((f"domain-{index}", lambda item, index=index:
                                 item["trust_domains"][index].__setitem__("production_implemented", True)))
    for index in range(14):
        fixture_mutators.append((f"control-{index}", lambda item, index=index:
                                 item["production_ingestion_controls"][index].__setitem__("implemented", True)))
    for index in range(20):
        fixture_mutators.append((f"threat-{index}", lambda item, index=index:
                                 item["threat_cases"][index].__setitem__("expected_disposition", "ACCEPTED")))
    for index in range(10):
        fixture_mutators.append((f"handoff-{index}", lambda item, index=index:
                                 item["owner_handoff_requirements"][index].__setitem__("satisfied", True)))
    for index in range(8):
        fixture_mutators.append((f"freshness-{index}", lambda item, index=index:
                                 item["freshness_requirements"][index].__setitem__("real_currentness_proved", True)))
    for key in boundary_fixture["nonclaims"]:
        fixture_mutators.append((f"nonclaim-{key}", lambda item, key=key:
                                 item["nonclaims"].__setitem__(key, "UNLOCKED" if key == "side_effects_unlocked" else True)))
    for key in boundary_fixture["expected"]:
        fixture_mutators.append((f"expected-{key}", lambda item, key=key:
                                 item["expected"].__setitem__(key, mutate_scalar(item["expected"][key]))))
    for index in range(4):
        fixture_mutators.append((f"gate-{index}", lambda item, index=index:
                                 item["downstream_separate_gates"].__setitem__(index, "MUTATED_GATE")))
    fixture_mutators.append(("tracks-swap", lambda item: item["tracks"].reverse()))
    for label, mutator in fixture_mutators:
        candidate = copy.deepcopy(boundary_fixture); mutator(candidate)
        expect_rejected(lambda c=candidate: validate_boundary_fixture(c, predecessor_fixture,
                                                                       enforce_hash=False), label + "-independent")
        expect_rejected(lambda c=candidate: reviewer.review(*documents, c), label + "-reviewer")
        counts["fixture_semantic_negatives"] += 1

    aggregate_mutators: list[tuple[str, Callable[[dict[str, Any]], None]]] = []
    for key in request:
        aggregate_mutators.append((f"request-drop-{key}", lambda item, key=key: item.pop(key)))
    aggregate_mutators.extend((
        ("request-extra", lambda item: item.__setitem__("extra", False)),
        ("request-schema", lambda item: item.__setitem__("schema", "wrong.schema")),
        ("request-version", lambda item: item.__setitem__("schema_version", 2)),
        ("request-mode", lambda item: item.__setitem__("mode", "PRODUCTION")),
        ("request-context", lambda item: item.__setitem__("synthetic_context_sha256", "0" * 64)),
        ("request-id", lambda item: item.__setitem__("request_id_sha256", "0" * 64)),
        ("request-order", lambda item: item["evidence_packets"].reverse()),
        ("request-duplicate", lambda item: item["evidence_packets"].__setitem__(1,
                                                                                copy.deepcopy(item["evidence_packets"][0]))),
    ))
    for index in range(15):
        aggregate_mutators.append((f"packet-id-{index}", lambda item, index=index:
                                   item["evidence_packets"][index].__setitem__("packet_id_sha256", "0" * 64)))
    aggregate_mutators.extend((
        ("packet-boundary", lambda item: item["evidence_packets"][0]["boundary"].__setitem__("runtime_authority", True)),
        ("packet-track", lambda item: item["evidence_packets"][1].__setitem__("track_partition", "SELF_HOSTED_ONLY")),
        ("packet15-dependency", lambda item: item["evidence_packets"][14]["payload"]["ordered_prerequisite_packet_id_sha256"].reverse()),
        ("owner-positive", lambda item: item["owner_packet"].__setitem__("decision_state", "APPROVED")),
        ("owner-set", lambda item: item["owner_packet"]["evidence_set_binding"].__setitem__("evidence_set_sha256", "0" * 64)),
        ("owner-authority", lambda item: item["owner_packet"]["boundary"].__setitem__("runtime_authority", True)),
    ))
    for label, mutator in aggregate_mutators:
        candidate = copy.deepcopy(request); mutator(candidate)
        if set(candidate) == set(request) and label not in {"request-id"}:
            candidate["request_id_sha256"] = derive_request_id(candidate)
        expect_rejected(lambda c=candidate: reviewer.validate_aggregate_request(*documents,
                                                                                boundary_fixture, c), label)
        counts["aggregate_semantic_negatives"] += 1

    for key in RECEIPT_KEYS:
        candidate = copy.deepcopy(receipt)
        candidate[key] = mutate_scalar(candidate[key])
        if key != "content_sha256":
            candidate["content_sha256"] = sha256_value(without_key(candidate, "content_sha256"))
        expect_rejected(lambda c=candidate: validate_receipt(c, module, request, expected_results,
                                                              predecessor_fixture, boundary_fixture),
                        f"receipt-{key}")
        counts["receipt_semantic_negatives"] += 1
    for index in range(16):
        candidate = copy.deepcopy(receipt)
        candidate["case_results"][index]["primary_reason"] = "MUTATED_REASON"
        candidate["case_results_sha256"] = sha256_value(candidate["case_results"])
        candidate["content_sha256"] = sha256_value(without_key(candidate, "content_sha256"))
        expect_rejected(lambda c=candidate: validate_receipt(c, module, request, expected_results,
                                                              predecessor_fixture, boundary_fixture),
                        f"receipt-case-{index}")
        counts["receipt_semantic_negatives"] += 1
    counts["directed_negative_tests"] = sum(
        counts[field]
        for field in (
            "json_guard_negatives",
            "fixture_semantic_negatives",
            "aggregate_semantic_negatives",
            "receipt_semantic_negatives",
        )
    )
    return counts


def evaluate(self_test: bool) -> str:
    check_decoder_guards()
    check_successor_source_purity()
    documents = verify_predecessor_artifacts()
    boundary_fixture = read_json(BOUNDARY_FIXTURE_REL)
    validate_boundary_fixture(boundary_fixture, documents[1])
    predecessor_name = Path(PREDECESSOR_MODULE_REL).stem
    successor_name = Path(SUCCESSOR_MODULE_REL).stem
    predecessor_module = load_module(PREDECESSOR_MODULE_REL, predecessor_name)
    module = load_module(SUCCESSOR_MODULE_REL, successor_name)
    suite, expected_results, _predecessor_receipt = call_predecessor_public_api(
        predecessor_module, documents
    )
    reviewer = module.RuntimePrerequisiteEvidencePacketOfflineIntegrationBoundaryReviewer()
    request = reviewer.known_answer_aggregate_request(*copy.deepcopy(documents),
                                                       copy.deepcopy(boundary_fixture))
    packet_ids = validate_request(request, suite, documents[1], documents[4])
    require(packet_ids == [row["packet_id_sha256"] for row in expected_results[:15]],
            "E_REQUEST_RESULTS", "packet order")
    receipt = reviewer.validate_aggregate_request(*copy.deepcopy(documents),
                                                  copy.deepcopy(boundary_fixture),
                                                  copy.deepcopy(request))
    rendered = validate_receipt(receipt, module, request, expected_results, documents[1],
                                boundary_fixture)
    require(reviewer.review(*copy.deepcopy(documents), copy.deepcopy(boundary_fixture)) == receipt,
            "E_REVIEW", "generate/validate equivalence")
    valid_owner_combinations = validate_owner_state_reason_matrix(
        module, documents, boundary_fixture, request
    )
    if not self_test:
        return rendered
    counts = run_self_test(module, documents, boundary_fixture, request,
                           receipt, expected_results, valid_owner_combinations)
    expected_counts = {
        "json_guard_negatives": 4,
        "fixture_semantic_negatives": 147,
        "aggregate_semantic_negatives": 36,
        "receipt_semantic_negatives": 66,
        "valid_owner_state_reason_combinations": 6,
        "directed_negative_tests": 253,
    }
    require(counts == expected_counts, "E_SELF_TEST_COUNTS", str(counts))
    return (
        "self_test\tPASS\n"
        f"directed_negative_tests\t{counts['directed_negative_tests']}\n"
        f"fixture_semantic_negative_tests\t{counts['fixture_semantic_negatives']}\n"
        f"aggregate_semantic_negative_tests\t{counts['aggregate_semantic_negatives']}\n"
        f"receipt_semantic_negative_tests\t{counts['receipt_semantic_negatives']}\n"
        f"json_guard_negative_tests\t{counts['json_guard_negatives']}\n"
        "predecessor_public_validator_calls\t16\n"
        f"valid_owner_state_reason_combinations\t{counts['valid_owner_state_reason_combinations']}\n"
        "source_ast_purity\tPASS\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        print(evaluate(args.self_test), end="")
    except (CheckError, ValueError, TypeError, KeyError, OSError) as error:
        print(f"offline integration boundary pack check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
