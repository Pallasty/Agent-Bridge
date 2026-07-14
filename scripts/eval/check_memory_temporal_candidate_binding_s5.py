#!/usr/bin/env python3
"""Fail-closed structural checker for the S5 synthetic candidate binding."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any


BASELINE = "486f04fb9a967a9a6cf5272f82f36cc0d7e787ad"
STATUS = "SYNTHETIC_CANDIDATE_INTERFACE_IMPLEMENTED_SCHEMA_COMPATIBLE_NOT_LIVE"
DECISION = "BLOCKED_FAIL_CLOSED"
FEATURE = "temporal-evidence-s5-candidate-synthetic"

CANDIDATE_SCHEMA_PATH = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-candidate-evidence-envelope-schema-v0.json"
)
CANDIDATE_SCHEMA = "agent_bridge.biocortex_ab_track_b_candidate_evidence_envelope.v0"
CANDIDATE_SCHEMA_SHA256 = (
    "edba8da90abeeda83e33943d9b87f76c0deff9fad34cb314cd27c28b85ed1b77"
)
TRUTH_REFERENT_SCHEMA_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-truth-referent-schema-v0.json"
)
TRUTH_REFERENT_SCHEMA_SHA256 = (
    "5da057e70675cbd259e0d1beb98039d2eee8589c73aa910f92f90cb0374545a8"
)
FOUNDATIONAL_MANIFEST_SHA256 = (
    "fbfbf5738dd81e0afe8dbc45b1e91a35e92382a1913006a9b2e5ded67c077f36"
)

S4_FROZEN_SHA256 = {
    "crates/store/src/sqlite/temporal_evidence/projection_v1.rs": (
        "24c086ae8c567ea629a13ec1291e1933ef1d615ac002b6b74f0ec82741af3388"
    ),
    "crates/bridge/src/memory_temporal_evidence_adapter_v1.rs": (
        "e706f8836cb54751f07beac551dd5a3090e7274b55b7fb64372507df33320668"
    ),
    "crates/store/src/sqlite/temporal_evidence.rs": (
        "f03a80f45c5c9e472ee68d05f10609c8edcd24ace3f1a5b2e521c68bf86a7299"
    ),
    "crates/store/src/sqlite.rs": (
        "34163933bb1df3d80eb0f0b88c49ce895b6157f8bab2d1232b12607263e623b8"
    ),
}

TRACK_B_FROZEN_SHA256 = {
    "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v0.json": (
        "ad40df50eec68fa192c79e6699a8d2da2a9c3925a387eaa7427f7e19f996d783"
    ),
    "docs/design/fixtures/biocortex-ab-track-b-review-command-schema-v0.json": (
        "40df0e39f36df01d414487c496cf09b5ffbed89cafc540dc89e6e57bea4466f5"
    ),
    "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v0.json": (
        "9e73afee2f6366a241b155680b4f77341adeb7c4e341ab91b8d4b1499b5aacbd"
    ),
    TRUTH_REFERENT_SCHEMA_PATH: TRUTH_REFERENT_SCHEMA_SHA256,
    "scripts/eval/fixtures/biocortex_ab_track_b_foundational_schema_pack_v0.json": (
        FOUNDATIONAL_MANIFEST_SHA256
    ),
    "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json": (
        "8f618659cb90cc311ef79aafa3fc536bacc3f428f82291998174a0e374d993af"
    ),
    "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json": (
        "764f063fefe0e516547f9bd1e71417242daf292d57e480ae39b73df8bcda341a"
    ),
    "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json": (
        "1508c0c990ccf9ce26fa0eb524194bb587816cc78d4546236c8d9c00dd3b306e"
    ),
}

REMAINING_GAPS = (
    "AUTHORITY_POLICY_CUSTODY_UNRESOLVED",
    "CAPTURE_PROVENANCE_UNATTESTED",
    "CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED",
    "PHYSICAL_PRIVACY_DELETION_UNRESOLVED",
    "PRODUCTION_PRODUCER_PROFILE_UNADMITTED",
)

TOP_FIELDS = (
    "authentication",
    "boundary",
    "candidate_evidence_schema_sha256",
    "candidate_id",
    "case_id",
    "claims",
    "contract_sha256",
    "expires_at_utc",
    "foundational_schema_pack_manifest_sha256",
    "handle_key_id",
    "handle_profile_id",
    "issued_at_utc",
    "limits",
    "projection_binding_handle",
    "request_id",
    "request_nonce",
    "schema",
    "trial_id",
    "truth_referent_schema_sha256",
)
AUTHENTICATION_FIELDS = (
    "algorithm",
    "canonicalization",
    "domain",
    "hmac_sha256",
    "key_id",
    "message_profile",
    "payload_sha256",
)
BOUNDARY_FIELDS = (
    "authority_custody_resolved",
    "biocortex_runtime_influence",
    "capture_provenance_attested",
    "contains_raw_evidence_ids",
    "contains_raw_predicate_ids",
    "contains_raw_provenance",
    "contains_raw_referent_ids",
    "contains_raw_source_bindings",
    "contains_raw_values",
    "cross_repository_transport_authorized",
    "live_binding_satisfied",
    "physical_privacy_deletion_resolved",
    "production_profile_active",
    "side_effects_unlocked",
)
CLAIM_FIELDS = (
    "claim_binding_hmac_sha256",
    "evidence_count",
    "evidence_handles",
    "noncurrent_evidence_count",
    "referent",
    "shadowed_evidence_count",
    "source_binding_handles",
    "supporting_evidence_handles",
    "temporal_state",
    "truth_state",
    "truth_tier",
    "value_handles",
)
REFERENT_FIELDS = ("claim_handle", "predicate_handle", "referent_handle")
LIMIT_FIELDS = (
    "max_claims",
    "max_envelope_bytes",
    "max_evidence_per_claim",
    "max_source_bindings_per_claim",
    "max_ttl_seconds",
    "max_values_per_claim",
)
PROJECTION_IDENTITY_FIELDS = (
    "as_of",
    "canonical_order",
    "knowledge_cutoff",
    "ledger_format_version",
    "mapping_version",
    "migration_sha256",
    "prepared_input_sha256",
    "producer_profile",
    "projection_mode",
    "projection_schema",
    "projection_sha256",
    "pruned_inbound_relationships",
    "query_only_attested",
    "read_only_attested",
    "schema_meta_version",
    "schema_sha256",
    "snapshot_counts",
    "snapshot_limits",
    "snapshot_payload_bytes",
    "snapshot_payload_sha256",
    "synthetic_fixture_id",
    "zero_total_changes_attested",
)


class CheckFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def path_for(repo: Path, relative: str) -> Path:
    path = repo / relative
    require(path.is_file(), f"missing required file: {relative}")
    require(not path.is_symlink(), f"symlink forbidden: {relative}")
    return path


def read(repo: Path, relative: str) -> str:
    return path_for(repo, relative).read_text(encoding="utf-8")


def sha256(repo: Path, relative: str) -> str:
    return hashlib.sha256(path_for(repo, relative).read_bytes()).hexdigest()


def compact(source: str) -> str:
    return re.sub(r"\s+", " ", source)


def struct_parts(source: str, name: str) -> tuple[str, str, str]:
    match = re.search(
        rf"(?P<prefix>(?:#\[[^\n]+\]\s*)*)"
        rf"(?P<visibility>pub(?:\([^)]*\))?\s+)?struct\s+{re.escape(name)}"
        rf"(?:<[^{{}}]+>)?\s*\{{(?P<body>.*?)\n\}}",
        source,
        re.DOTALL,
    )
    require(match is not None, f"missing struct {name}")
    return match.group("prefix"), (match.group("visibility") or "").strip(), match.group("body")


def rust_field_names(body: str) -> set[str]:
    return set(
        re.findall(
            r"^\s*(?:pub(?:\([^)]*\))?\s+)?([a-z][a-z0-9_]*)\s*:",
            body,
            re.MULTILINE,
        )
    )


def require_exact_fields(body: str, expected: tuple[str, ...], label: str) -> None:
    actual = rust_field_names(body)
    require(actual == set(expected), f"{label} fields drift: {sorted(actual)}")


def require_schema_object(schema: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    require(schema.get("type") == "object", f"{label} must be an object")
    require(schema.get("additionalProperties") is False, f"{label} must reject additional properties")
    require(schema.get("unevaluatedProperties") is False, f"{label} must reject unevaluated properties")
    properties = schema.get("properties")
    required = schema.get("required")
    require(isinstance(properties, dict), f"{label} properties missing")
    require(list(properties) == list(fields), f"{label} property order/set drift")
    require(required == list(fields), f"{label} required order/set drift")


def walk_json(value: Any) -> list[Any]:
    found = [value]
    if isinstance(value, dict):
        for child in value.values():
            found.extend(walk_json(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(walk_json(child))
    return found


def check_schema(repo: Path) -> None:
    raw = read(repo, CANDIDATE_SCHEMA_PATH)
    require(sha256(repo, CANDIDATE_SCHEMA_PATH) == CANDIDATE_SCHEMA_SHA256, "candidate schema digest drift")
    schema = json.loads(raw)
    canonical = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    require(raw == canonical, "candidate schema is not canonical sorted pretty JSON")
    require(
        list(schema) == [
            "$defs",
            "$id",
            "$schema",
            "additionalProperties",
            "description",
            "properties",
            "required",
            "title",
            "type",
            "unevaluatedProperties",
        ],
        "candidate schema top-level vocabulary drift",
    )
    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "schema draft drift")
    require(
        schema.get("$id") == "urn:agent-bridge:biocortex-ab:track-b:candidate-evidence-envelope:v0",
        "candidate schema id drift",
    )
    require_schema_object(schema, TOP_FIELDS, "candidate envelope")

    definitions = schema.get("$defs")
    require(isinstance(definitions, dict), "candidate schema definitions missing")
    require(
        list(definitions)
        == [
            "authentication",
            "boundary",
            "caseId",
            "claim",
            "claimHandle",
            "evidenceHandle",
            "label",
            "limits",
            "predicateHandle",
            "projectionHandle",
            "referent",
            "referentHandle",
            "sha256",
            "sourceHandle",
            "valueHandle",
        ],
        "candidate schema definition set drift",
    )
    require_schema_object(definitions["authentication"], AUTHENTICATION_FIELDS, "authentication")
    require_schema_object(definitions["boundary"], BOUNDARY_FIELDS, "boundary")
    require_schema_object(definitions["claim"], CLAIM_FIELDS, "claim")
    require_schema_object(definitions["limits"], LIMIT_FIELDS, "limits")
    require_schema_object(definitions["referent"], REFERENT_FIELDS, "referent")

    for node in walk_json(schema):
        if isinstance(node, dict) and node.get("type") == "object":
            require(node.get("additionalProperties") is False, "open object found in candidate schema")
            require(node.get("unevaluatedProperties") is False, "unevaluated object found in candidate schema")
        if isinstance(node, dict) and "$ref" in node:
            reference = node["$ref"]
            require(
                isinstance(reference, str)
                and reference.startswith("#/$defs/")
                and reference.removeprefix("#/$defs/") in definitions,
                f"non-local or unresolved schema reference: {reference}",
            )

    authentication = definitions["authentication"]["properties"]
    require(authentication["algorithm"] == {"const": "HMAC-SHA-256"}, "authentication algorithm drift")
    require(
        authentication["canonicalization"]
        == {"const": "serde_json_compact_struct_field_order_utf8_v1"},
        "authentication canonicalization drift",
    )
    require(
        authentication["domain"]
        == {"const": "agent-bridge/track-b/candidate-evidence-envelope/v0"},
        "authentication domain drift",
    )
    require(
        authentication["message_profile"]
        == {"const": "u64be_len_domain_domain_u64be_len_key_id_key_id_exact_payload_json"},
        "authentication message profile drift",
    )
    for field in ("hmac_sha256", "payload_sha256"):
        require(authentication[field] == {"$ref": "#/$defs/sha256"}, f"{field} definition drift")
    require(authentication["key_id"] == {"$ref": "#/$defs/label"}, "protected key id definition drift")

    boundary = definitions["boundary"]["properties"]
    for field in BOUNDARY_FIELDS:
        expected = {"const": "NONE"} if field == "side_effects_unlocked" else {"const": False}
        require(boundary[field] == expected, f"boundary must remain closed: {field}")

    require(
        definitions["caseId"]
        == {"maxLength": 37, "minLength": 37, "pattern": "^case_[0-9a-f]{32}$", "type": "string"},
        "strict case id definition drift",
    )
    require(
        definitions["label"]
        == {
            "maxLength": 128,
            "minLength": 1,
            "pattern": "^[a-z0-9][a-z0-9_.:-]{0,127}$",
            "type": "string",
        },
        "lowercase label definition drift",
    )
    require(
        definitions["sha256"]
        == {"maxLength": 64, "minLength": 64, "pattern": "^[0-9a-f]{64}$", "type": "string"},
        "sha256 definition drift",
    )
    for name, prefix in (
        ("claimHandle", "clm"),
        ("evidenceHandle", "evd"),
        ("predicateHandle", "prd"),
        ("projectionHandle", "prj"),
        ("referentHandle", "ref"),
        ("sourceHandle", "src"),
        ("valueHandle", "val"),
    ):
        require(
            definitions[name]
            == {
                "maxLength": 36,
                "minLength": 36,
                "pattern": f"^{prefix}_[0-9a-f]{{32}}$",
                "type": "string",
            },
            f"{name} definition drift",
        )

    limits = definitions["limits"]["properties"]
    require(
        {name: limits[name].get("const") for name in LIMIT_FIELDS}
        == {
            "max_claims": 1023,
            "max_envelope_bytes": 4194303,
            "max_evidence_per_claim": 1023,
            "max_source_bindings_per_claim": 1023,
            "max_ttl_seconds": 3599,
            "max_values_per_claim": 1023,
        },
        "inclusive limit definitions drift",
    )
    claim = definitions["claim"]["properties"]
    for field in ("evidence_count", "noncurrent_evidence_count", "shadowed_evidence_count"):
        require(
            claim[field] == {"maximum": 1023, "minimum": 0, "type": "integer"},
            f"{field} cap drift",
        )
    for field, item_ref in (
        ("evidence_handles", "evidenceHandle"),
        ("supporting_evidence_handles", "evidenceHandle"),
        ("source_binding_handles", "sourceHandle"),
        ("value_handles", "valueHandle"),
    ):
        require(
            claim[field]
            == {
                "items": {"$ref": f"#/$defs/{item_ref}"},
                "maxItems": 1023,
                "type": "array",
                "uniqueItems": True,
            },
            f"{field} cap or handle type drift",
        )
    require(claim["referent"] == {"$ref": "#/$defs/referent"}, "claim referent definition drift")
    require(
        claim["temporal_state"] == {"enum": ["current", "future", "historical", "indeterminate"]},
        "temporal state labels drift",
    )
    require(
        claim["truth_state"] == {"enum": ["conflicted", "supported", "unknown"]},
        "truth state labels drift",
    )
    require(
        claim["truth_tier"]
        == {"enum": ["authoritative", "inferred", "none", "observed", "verified"]},
        "truth tier labels drift",
    )

    properties = schema["properties"]
    require(properties["schema"] == {"const": CANDIDATE_SCHEMA}, "candidate schema label drift")
    require(
        properties["candidate_id"]
        == {"const": "temporal_truth_projection_v1_synthetic_source_binding"},
        "candidate id drift",
    )
    require(
        properties["handle_profile_id"]
        == {"const": "request_scoped_hmac_sha256_trunc128_v1"},
        "handle profile drift",
    )
    require(
        properties["candidate_evidence_schema_sha256"] == {"$ref": "#/$defs/sha256"},
        "self-reported candidate schema digest shape drift",
    )
    require(
        properties["foundational_schema_pack_manifest_sha256"]
        == {"const": FOUNDATIONAL_MANIFEST_SHA256},
        "foundational manifest digest must be schema-bound",
    )
    require(
        properties["truth_referent_schema_sha256"]
        == {"const": TRUTH_REFERENT_SCHEMA_SHA256},
        "truth referent digest must be schema-bound",
    )
    require(
        properties["claims"]
        == {
            "items": {"$ref": "#/$defs/claim"},
            "maxItems": 1023,
            "minItems": 1,
            "type": "array",
            "uniqueItems": True,
        },
        "top-level claim cap drift",
    )
    for field in ("issued_at_utc", "expires_at_utc"):
        require(
            properties[field].get("type") == "integer"
            and properties[field].get("minimum") == 0
            and properties[field].get("maximum") == 9223372036854775807,
            f"{field} must remain non-negative signed i64 Unix seconds",
        )

    truth_schema = json.loads(read(repo, TRUTH_REFERENT_SCHEMA_PATH))
    require(sha256(repo, TRUTH_REFERENT_SCHEMA_PATH) == TRUTH_REFERENT_SCHEMA_SHA256, "truth referent drift")
    for name in ("claimHandle", "predicateHandle", "referentHandle"):
        require(definitions[name] == truth_schema["$defs"][name], f"truth referent handle incompatibility: {name}")
    for key in ("type", "additionalProperties", "unevaluatedProperties", "properties", "required"):
        require(definitions["referent"][key] == truth_schema[key], f"truth referent object incompatibility: {key}")


def check_rust_and_cargo(repo: Path) -> None:
    store_cargo = tomllib.loads(read(repo, "crates/store/Cargo.toml"))
    bridge_cargo = tomllib.loads(read(repo, "crates/bridge/Cargo.toml"))
    require(store_cargo["features"]["default"] == ["onnx-embed"], "store default feature drift")
    require(
        store_cargo["features"].get(FEATURE)
        == ["temporal-evidence-s4-synthetic", "dep:ring"],
        "store S5 feature must only add S4 and ring",
    )
    ring_dependency = store_cargo["dependencies"].get("ring")
    require(
        isinstance(ring_dependency, dict)
        and ring_dependency.get("version") == "0.17"
        and ring_dependency.get("optional") is True,
        "ring 0.17 must remain optional",
    )
    require(bridge_cargo["features"]["default"] == ["onnx-embed"], "bridge default feature drift")
    require(
        bridge_cargo["features"].get(FEATURE)
        == ["temporal-evidence-s4-synthetic", f"ab-store/{FEATURE}"],
        "bridge S5 feature forwarding drift",
    )
    lock = tomllib.loads(read(repo, "Cargo.lock"))
    store_packages = [package for package in lock["package"] if package.get("name") == "ab-store"]
    require(len(store_packages) == 1, "Cargo.lock ab-store package missing or duplicated")
    require("ring" in store_packages[0].get("dependencies", []), "Cargo.lock does not bind ring to ab-store")
    require(
        any(
            package.get("name") == "ring" and str(package.get("version", "")).startswith("0.17.")
            for package in lock["package"]
        ),
        "Cargo.lock ring 0.17 package missing",
    )

    candidate = read(repo, "crates/store/src/temporal_candidate_evidence.rs")
    flat = compact(candidate)
    store_lib = read(repo, "crates/store/src/lib.rs")
    bridge_lib = read(repo, "crates/bridge/src/lib.rs")
    bridge_wrapper = read(repo, "crates/bridge/src/memory_track_b_candidate_evidence_v1.rs")
    tests = read(repo, "crates/store/src/sqlite/temporal_evidence/tests.rs")

    require(
        f'#[cfg(feature = "{FEATURE}")]\nmod temporal_candidate_evidence;' in store_lib,
        "store S5 module must be feature-gated and private",
    )
    require("pub mod temporal_candidate_evidence" not in store_lib, "public store S5 module forbidden")
    require(
        f'#[cfg(feature = "{FEATURE}")]' in bridge_lib
        and "pub(crate) mod memory_track_b_candidate_evidence_v1;" in bridge_lib,
        "bridge S5 module must be feature-gated and crate-private",
    )
    require(
        "pub(crate) fn bind_synthetic_track_b_candidate_evidence_v1" in bridge_wrapper,
        "crate-private bridge wrapper missing",
    )
    require(
        not re.search(r"(?<!\(crate\) )pub\s+fn\s+bind_synthetic_track_b_candidate_evidence_v1", bridge_wrapper),
        "public bridge wrapper forbidden",
    )

    require("use ring::hmac;" in candidate, "S5 must use audited ring HMAC")
    require("hmac::HMAC_SHA256" in candidate, "ring HMAC-SHA-256 primitive missing")
    constants = {
        "AUTHENTICATION_DOMAIN": "agent-bridge/track-b/candidate-evidence-envelope/v0",
        "REQUEST_BINDING_DOMAIN": "agent-bridge/track-b/candidate-evidence/request-binding/v1",
        "HANDLE_SCOPE_DOMAIN": "agent-bridge/track-b/candidate-evidence/handle-scope/v1",
        "PROJECTION_HANDLE_DOMAIN": "agent-bridge/track-b/candidate-evidence/projection-handle/v1",
        "CLAIM_HANDLE_DOMAIN": "agent-bridge/track-b/candidate-evidence/claim-handle/v1",
        "REFERENT_HANDLE_DOMAIN": "agent-bridge/track-b/candidate-evidence/referent-handle/v1",
        "PREDICATE_HANDLE_DOMAIN": "agent-bridge/track-b/candidate-evidence/predicate-handle/v1",
        "VALUE_HANDLE_DOMAIN": "agent-bridge/track-b/candidate-evidence/value-handle/v1",
        "EVIDENCE_HANDLE_DOMAIN": "agent-bridge/track-b/candidate-evidence/evidence-handle/v1",
        "SOURCE_HANDLE_DOMAIN": "agent-bridge/track-b/candidate-evidence/source-handle/v1",
        "CLAIM_BINDING_DOMAIN": "agent-bridge/track-b/candidate-evidence/claim-binding/v1",
    }
    for name, value in constants.items():
        require(name in candidate and value in candidate, f"candidate HMAC domain drift: {name}")
    require(len(set(constants.values())) == len(constants), "candidate HMAC domains must be distinct")
    for token in (
        'const HMAC_ALGORITHM: &str = "HMAC-SHA-256";',
        'const AUTHENTICATION_CANONICALIZATION: &str = "serde_json_compact_struct_field_order_utf8_v1";',
        '"u64be_len_domain_domain_u64be_len_key_id_key_id_exact_payload_json";',
        "context.update(&(bytes.len() as u64).to_be_bytes()); context.update(bytes);",
        "update_framed(&mut writer.hmac, domain); update_framed(&mut writer.hmac, key_id);",
        "self.sha256.update(buffer); self.hmac.update(buffer);",
        "serde_json::to_writer(&mut writer, &payload)",
        "AuthenticatedPayloadWriter::new( &permit.transport_key, AUTHENTICATION_DOMAIN.as_bytes(), permit.transport_key_id.as_bytes(), )",
    ):
        require(token in flat, f"authentication framing token missing: {token}")

    for token in (
        "const MAX_CLAIMS: usize = 1_024;",
        "const MAX_VALUES_PER_CLAIM: usize = 1_024;",
        "const MAX_EVIDENCE_PER_CLAIM: usize = 1_024;",
        "const MAX_SOURCE_BINDINGS_PER_CLAIM: usize = 1_024;",
        "const MAX_ENVELOPE_BYTES: usize = 4 * 1024 * 1024;",
        "const MAX_TTL_SECONDS: i64 = 3_600;",
        "if value >= sentinel",
        "if next >= MAX_ENVELOPE_BYTES",
        "max_claims: MAX_CLAIMS - 1",
        "max_envelope_bytes: MAX_ENVELOPE_BYTES - 1",
        "max_evidence_per_claim: MAX_EVIDENCE_PER_CLAIM - 1",
        "max_source_bindings_per_claim: MAX_SOURCE_BINDINGS_PER_CLAIM - 1",
        "max_ttl_seconds: MAX_TTL_SECONDS - 1",
        "max_values_per_claim: MAX_VALUES_PER_CLAIM - 1",
    ):
        require(token in flat, f"inclusive-limit implementation token missing: {token}")

    permit_prefix, permit_visibility, permit_body = struct_parts(
        candidate, "SyntheticTrackBCandidateEvidencePermitV1"
    )
    require(permit_visibility == "pub", "permit type visibility drift")
    require("pub " not in permit_body, "permit fields must remain private")
    for forbidden in ("Clone", "Copy", "Default", "Serialize", "Deserialize"):
        require(forbidden not in permit_prefix, f"permit must not derive {forbidden}")
        require(
            not re.search(
                rf"impl\s+(?:serde::)?{forbidden}\s+for\s+SyntheticTrackBCandidateEvidencePermitV1",
                candidate,
            ),
            f"manual permit {forbidden} impl forbidden",
        )
    require("impl Drop for SyntheticTrackBCandidateEvidencePermitV1" in candidate, "permit drop clearing missing")
    require(
        "self.handle_key.fill(0); self.request_nonce.fill(0); self.transport_key.fill(0);" in flat,
        "permit key/nonce clearing drift",
    )
    constructor = re.search(
        r"(?P<prefix>(?:#\[[^\n]+\]\s*)+)pub\(crate\)\s+fn\s+"
        r"synthetic_track_b_candidate_evidence_permit_v1\s*\(.*?\)\s*->\s*"
        r"CandidateResult<SyntheticTrackBCandidateEvidencePermitV1>",
        candidate,
        re.DOTALL,
    )
    require(constructor is not None, "test-only permit constructor missing")
    require("#[cfg(test)]" in constructor.group("prefix"), "permit constructor must be cfg(test)")
    require(
        len(re.findall(r"fn\s+\w+\s*\(.*?\)\s*->\s*CandidateResult<SyntheticTrackBCandidateEvidencePermitV1>", candidate, re.DOTALL))
        == 1,
        "permit must have exactly one safe constructor",
    )
    require(
        '#[cfg(all(test, feature = "temporal-evidence-s5-candidate-synthetic"))]\n'
        "pub(crate) use temporal_candidate_evidence::synthetic_track_b_candidate_evidence_permit_v1;"
        in store_lib,
        "permit reexport must remain test-only",
    )

    pair_prefix, pair_visibility, pair_body = struct_parts(
        candidate, "SyntheticTrackBCandidateProjectionPairV1"
    )
    require(pair_visibility == "pub", "request/projection pair visibility drift")
    require("pub " not in pair_body, "request/projection pair fields must remain private")
    require_exact_fields(pair_body, ("projection", "request"), "request/projection pair")
    for forbidden in ("Clone", "Copy", "Default", "Serialize", "Deserialize"):
        require(forbidden not in pair_prefix, f"request/projection pair must not derive {forbidden}")
        require(
            not re.search(
                rf"impl\s+(?:serde::)?{forbidden}\s+for\s+SyntheticTrackBCandidateProjectionPairV1",
                candidate,
            ),
            f"manual request/projection-pair {forbidden} impl forbidden",
        )
    fused = compact(
        candidate[
            candidate.index("pub async fn project_synthetic_track_b_candidate_source_v1") :
            candidate.index("/// One-shot synthetic capability", candidate.index("pub async fn project_synthetic_track_b_candidate_source_v1"))
        ]
    )
    for token in (
        "permit: SyntheticTemporalTruthProjectionPermitV1",
        "path: &Path",
        "request: TemporalTruthProjectionRequestV1",
        "CandidateResult<SyntheticTrackBCandidateProjectionPairV1>",
        "temporal_truth_project_read_only_synthetic_v1(permit, path, request.clone()) .await",
        "Ok(SyntheticTrackBCandidateProjectionPairV1 { projection, request, })",
    ):
        require(token in fused, f"fused S4 pair constructor invariant missing: {token}")
    require(
        candidate.count("Ok(SyntheticTrackBCandidateProjectionPairV1 {") == 1,
        "request/projection pair must have one construction site",
    )
    constructor_signature = compact(constructor.group(0))
    require(
        "pair: &SyntheticTrackBCandidateProjectionPairV1" in constructor_signature,
        "permit constructor must accept only the inseparable pair",
    )
    require(
        "BoundTemporalTruthProjectionV1" not in constructor_signature
        and "TemporalTruthProjectionRequestV1" not in constructor_signature,
        "permit constructor must not accept retrofit request/projection arguments",
    )

    bound_prefix, bound_visibility, bound_body = struct_parts(candidate, "BoundTrackBCandidateEvidenceV1")
    require(bound_visibility == "pub", "bound result visibility drift")
    require("pub " not in bound_body, "bound result fields must remain private")
    require_exact_fields(
        bound_body,
        (
            "authentication",
            "case_id",
            "claims",
            "contract_sha256",
            "expires_at_utc",
            "handle_key_id",
            "issued_at_utc",
            "projection_binding_handle",
            "request_id",
            "request_nonce",
            "trial_id",
        ),
        "bound result",
    )
    for forbidden in ("Clone", "Default", "Serialize", "Deserialize"):
        require(forbidden not in bound_prefix, f"bound result must not derive {forbidden}")
        require(
            not re.search(rf"impl\s+(?:serde::)?{forbidden}\s+for\s+BoundTrackBCandidateEvidenceV1", candidate),
            f"manual bound-result {forbidden} impl forbidden",
        )
    for forbidden_type in (
        "BoundTemporalTruthProjectionV1",
        "TemporalTruthProjectionRequestV1",
        "ProjectionBindingWire",
        "SyntheticTrackBCandidateEvidencePermitV1",
    ):
        require(forbidden_type not in bound_body, f"bound result retains source object: {forbidden_type}")
    require("handle_key:" not in bound_body and "transport_key:" not in bound_body, "bound result retains key material")

    projection_prefix, projection_visibility, projection_body = struct_parts(candidate, "ProjectionBindingWire")
    require(projection_visibility == "", "projection identity wire must remain private")
    require("Serialize" in projection_prefix and "PartialEq" in projection_prefix, "projection identity comparison markers missing")
    require_exact_fields(projection_body, PROJECTION_IDENTITY_FIELDS, "projection identity")
    projection_factory = candidate[
        candidate.index("impl ProjectionBindingWire") : candidate.index("#[derive(Serialize)]\nstruct RequiredClaimWire")
    ]
    for getter in (
        "as_of()",
        "canonical_order()",
        "knowledge_cutoff()",
        "ledger_format_version()",
        "mapping_version()",
        "migration_sha256()",
        "prepared_input_sha256()",
        "producer_profile()",
        "mode()",
        "schema()",
        "projection_sha256()",
        "pruned_inbound_relationships()",
        "query_only_attested()",
        "read_only_attested()",
        "schema_meta_version()",
        "schema_sha256()",
        "snapshot_counts()",
        "snapshot_limits()",
        "snapshot_payload_bytes()",
        "snapshot_payload_sha256()",
        "synthetic_fixture_id()",
        "zero_total_changes_attested()",
    ):
        require(f"projection.{getter}" in projection_factory, f"projection identity getter missing: {getter}")

    bind_start = candidate.index("pub fn bind_synthetic_track_b_candidate_evidence_v1")
    bind_end = candidate.index("#[cfg(test)]\nmod tests", bind_start)
    bind = compact(candidate[bind_start:bind_end])
    for token in (
        "permit: SyntheticTrackBCandidateEvidencePermitV1",
        "pair: SyntheticTrackBCandidateProjectionPairV1",
        "let SyntheticTrackBCandidateProjectionPairV1 { projection, request, } = pair",
        "let current_projection = ProjectionBindingWire::from_projection(&projection);",
        "if current_projection != permit.expected_projection",
        "if request_binding_sha256 != permit.expected_request_binding_sha256",
        "if evaluated_at_utc < permit.issued_at_utc || evaluated_at_utc >= permit.expires_at_utc",
        "let required_claims: BTreeSet<(&str, &str)> = request",
        "let projected_claims: BTreeSet<(&str, &str)> = projection",
        "if projected_claims != required_claims || projected_claims.len() != projected_claim_count",
    ):
        require(token in bind, f"source binding invariant missing: {token}")
    bind_signature = bind[: bind.index(") -> CandidateResult<BoundTrackBCandidateEvidenceV1>")]
    require(
        "request: TemporalTruthProjectionRequestV1" not in bind_signature
        and "projection: BoundTemporalTruthProjectionV1" not in bind_signature,
        "binder must not accept naked request/projection arguments",
    )
    bridge_flat = compact(bridge_wrapper)
    require(
        "permit: SyntheticTrackBCandidateEvidencePermitV1, pair: SyntheticTrackBCandidateProjectionPairV1, evaluated_at_utc: i64"
        in bridge_flat,
        "Bridge wrapper must consume only permit, pair, and evaluation time",
    )
    require(
        "TemporalTruthProjectionRequestV1" not in bridge_wrapper
        and "BoundTemporalTruthProjectionV1" not in bridge_wrapper,
        "Bridge wrapper must not accept naked request/projection arguments",
    )
    require(
        "if issued_at_utc < 0 || ttl <= 0 || ttl >= MAX_TTL_SECONDS" in flat,
        "permit TTL sentinel check missing",
    )

    for label, getter, limit in (
        ("values", "claim.values().len()", "MAX_VALUES_PER_CLAIM"),
        ("evidence", "claim.evidence_ids().len()", "MAX_EVIDENCE_PER_CLAIM"),
        ("supporting_evidence", "claim.supporting_evidence_ids().len()", "MAX_EVIDENCE_PER_CLAIM"),
        ("shadowed_evidence", "claim.shadowed_evidence_ids().len()", "MAX_EVIDENCE_PER_CLAIM"),
        ("noncurrent_evidence", "claim.noncurrent_evidence_ids().len()", "MAX_EVIDENCE_PER_CLAIM"),
        ("source_bindings", "claim.source_bindings().len()", "MAX_SOURCE_BINDINGS_PER_CLAIM"),
    ):
        require(
            re.search(
                rf'ensure_below_sentinel\(\s*"{label}",\s*{re.escape(getter)},\s*{limit},?\s*\)\?;',
                bind,
            )
            is not None,
            f"classification capacity check missing: {label}",
        )
    for token in (
        "evidence_count: claim.evidence_ids().len()",
        "let mut evidence_handles = Vec::with_capacity(claim.evidence_ids().len())",
        "let mut supporting_evidence_handles = Vec::with_capacity(claim.supporting_evidence_ids().len())",
        "model.evidence_count != model.evidence_handles.len()",
        "TemporalTruthStateV1::Supported => model.value_handles.len() == 1",
        "TemporalTruthStateV1::Conflicted => model.value_handles.len() >= 2",
        "TemporalTruthStateV1::Unknown =>",
        "model.supporting_evidence_handles.is_empty()",
        "model.source_binding_handles.is_empty()",
    ):
        require(token in flat, f"claim/evidence invariant missing: {token}")

    for constant, value in (
        ("TRACK_B_CANDIDATE_EVIDENCE_SCHEMA_SHA256", CANDIDATE_SCHEMA_SHA256),
        ("TRACK_B_FOUNDATIONAL_PACK_MANIFEST_SHA256", FOUNDATIONAL_MANIFEST_SHA256),
        (
            "TRACK_B_FOUNDATIONAL_ARTIFACT_CATALOG_SHA256",
            "bdee820dba3f20bae415826382551bf74cc9b6f13e51d2f9b1c49d9f9394d684",
        ),
        ("TRACK_B_TRUTH_REFERENT_SCHEMA_SHA256", TRUTH_REFERENT_SCHEMA_SHA256),
        ("S2_SCHEMA_SHA256", "6d321d45aafe65ef06efb49c46ccf9f1931624aada9e8873d7e29765826e3aa0"),
        ("S2_MIGRATION_SHA256", "f0d9a3a2505d301a266bb41c09ce2fbaebd8572aa9340affd7e62b6d29faa8bb"),
    ):
        require(constant in candidate and value in candidate, f"source identity constant drift: {constant}")
    for token in (
        "projection.schema() != TEMPORAL_TRUTH_PROJECTION_V1_SCHEMA",
        "projection.mode() != TEMPORAL_TRUTH_PROJECTION_V1_MODE",
        "projection.producer_profile() != TEMPORAL_TRUTH_PROJECTION_V1_PROFILE",
        "projection.mapping_version() != TEMPORAL_TRUTH_PROJECTION_V1_MAPPING",
        'projection.synthetic_fixture_id() != "crate_unit_test_only_v0"',
        'projection.schema_meta_version() != "43"',
        "projection.schema_sha256() != S2_SCHEMA_SHA256",
        "projection.migration_sha256() != S2_MIGRATION_SHA256",
        "projection.ledger_format_version() != 0",
        'projection.canonical_order() != "binary_utf8_v0"',
        "!projection.read_only_attested()",
        "!projection.query_only_attested()",
        "!projection.zero_total_changes_attested()",
    ):
        require(token in flat, f"S4 projection admission token missing: {token}")

    s5_tests = len(
        re.findall(
            r"(?:async\s+)?fn\s+temporal_truth_candidate_binding_s5_",
            candidate + "\n" + tests,
        )
    )
    s4_tests = len(re.findall(r"(?:async\s+)?fn\s+temporal_truth_projection_s4_", tests))
    s2_tests = len(re.findall(r"(?:async\s+)?fn\s+truth_evidence_s2_", tests))
    require(s5_tests == 7, f"S5 test count must be seven, got {s5_tests}")
    require(s4_tests == 7, f"S4 test count must be seven, got {s4_tests}")
    require(s2_tests == 14, f"S2 regression count must be fourteen, got {s2_tests}")
    for name in (
        "is_deterministic_opaque_and_source_bound",
        "nonce_changes_every_scope_binding",
        "rejects_empty_or_ambient_claim_sets",
        "rejects_same_projection_hash_snapshot_mix",
        "rejects_request_mix_and_match",
        "rejects_key_and_ttl_sentinels",
        "hmac_domain_framing_known_answer",
    ):
        require(name in candidate + tests, f"missing S5 adversarial test: {name}")

    state_store_suffix = store_lib[store_lib.index("pub trait StateStore") :]
    for token in (
        "bind_synthetic_track_b_candidate_evidence_v1",
        "BoundTrackBCandidateEvidenceV1",
        "SyntheticTrackBCandidateEvidencePermitV1",
    ):
        require(token not in state_store_suffix, f"S5 API entered StateStore: {token}")

    allowed_bridge = {
        repo / "crates/bridge/src/lib.rs",
        repo / "crates/bridge/src/memory_track_b_candidate_evidence_v1.rs",
    }
    for path in (repo / "crates/bridge/src").rglob("*.rs"):
        if path in allowed_bridge:
            continue
        source = path.read_text(encoding="utf-8")
        for token in (
            "bind_synthetic_track_b_candidate_evidence_v1",
            "BoundTrackBCandidateEvidenceV1",
            "SyntheticTrackBCandidateEvidencePermitV1",
        ):
            require(token not in source, f"unexpected Bridge/MCP runtime caller: {path.relative_to(repo)}")

    allowed_store = {
        repo / "crates/store/src/lib.rs",
        repo / "crates/store/src/temporal_candidate_evidence.rs",
        repo / "crates/store/src/sqlite/temporal_evidence/tests.rs",
    }
    for path in (repo / "crates/store/src").rglob("*.rs"):
        if path in allowed_store:
            continue
        source = path.read_text(encoding="utf-8")
        require(
            "bind_synthetic_track_b_candidate_evidence_v1" not in source,
            f"unexpected store runtime caller: {path.relative_to(repo)}",
        )


def check_docs(repo: Path) -> None:
    design = read(repo, "docs/design/MEMORY_TEMPORAL_CANDIDATE_BINDING_S5_2026_07_14.md")
    report = read(repo, "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-candidate-binding-s5.md")
    require(STATUS in design, "design status must remain schema-compatible and NOT_LIVE")
    require(DECISION in design and DECISION in report, "S5 decision must remain BLOCKED_FAIL_CLOSED")
    require("schema-compatible but not\nlive-bound" in report, "report must preserve not-live-bound status")
    for document_name, document in (("design", design), ("report", report)):
        for statement in (
            "source_artifact_compatibility_binding=true",
            "source_artifact_binding_satisfied=false",
            "track_b_artifact_binding_satisfied=false",
            "track_b_live_binding_satisfied=false",
        ):
            require(statement in document, f"{document_name} binding boundary drift: {statement}")
        for code in REMAINING_GAPS:
            require(code in document, f"{document_name} remaining gap missing: {code}")
    report_remaining = report[
        report.index("## Remaining state") : report.index("## Bound S5 sources")
    ]
    require(
        "CANDIDATE_EVIDENCE_INTERFACE_UNIMPLEMENTED" not in report_remaining,
        "resolved S5 interface gap remains in report gap set",
    )
    for statement in (
        "candidate_context_builder_bound=false",
        "truth_manifest_binding_satisfied=false",
        "nonce_single_use_registry_implemented=false",
        "real_capture_authorized=false",
        "production_profile_active=false",
        "mcp_surface_present=false",
        "state_store_surface_present=false",
        "biocortex_runtime_influence=false",
        "side_effects_unlocked=NONE",
        "decision=BLOCKED_FAIL_CLOSED",
    ):
        require(statement in report_remaining, f"report fail-closed boundary missing: {statement}")
    require("reports no latency" in design, "design must reject unsupported performance claims")
    require("provides no performance numbers" in report, "report must reject unsupported performance claims")


def check(repo: Path) -> list[tuple[str, str]]:
    for relative, expected in S4_FROZEN_SHA256.items():
        actual = sha256(repo, relative)
        require(actual == expected, f"frozen S4 drift: {relative}: {actual}")
    for relative, expected in TRACK_B_FROZEN_SHA256.items():
        actual = sha256(repo, relative)
        require(actual == expected, f"frozen Track B drift: {relative}: {actual}")

    check_schema(repo)
    check_rust_and_cargo(repo)
    check_docs(repo)

    return [
        ("schema", "agent_bridge.memory_temporal_candidate_binding_s5_receipt.v0"),
        ("status", STATUS),
        ("baseline_commit", BASELINE),
        ("candidate_schema", CANDIDATE_SCHEMA),
        ("candidate_schema_sha256", CANDIDATE_SCHEMA_SHA256),
        ("candidate_schema_canonical", "true"),
        ("candidate_schema_closed", "true"),
        ("truth_referent_schema_compatible", "true"),
        ("feature", FEATURE),
        ("feature_default", "false"),
        ("ring_hmac_dependency", "true"),
        ("safe_non_test_permit_constructor", "false"),
        ("permit_cloneable", "false"),
        ("projection_pair_cloneable", "false"),
        ("result_serializable", "false"),
        ("result_cloneable", "false"),
        ("result_retains_projection", "false"),
        ("inseparable_projection_pair", "true"),
        ("fused_s4_pair_constructor", "true"),
        ("retrofit_request_surface_present", "false"),
        ("exact_claim_set_required", "true"),
        ("complete_projection_identity_bound", "true"),
        ("bind_time_ttl_checked", "true"),
        ("authentication_algorithm", "HMAC-SHA-256"),
        ("authentication_domain", "agent-bridge/track-b/candidate-evidence-envelope/v0"),
        ("authentication_canonicalization", "serde_json_compact_struct_field_order_utf8_v1"),
        (
            "authentication_message_profile",
            "u64be_len_domain_domain_u64be_len_key_id_key_id_exact_payload_json",
        ),
        ("candidate_domain_separation", "true"),
        ("protected_key_id", "true"),
        ("request_scoped_handles", "true"),
        ("top_evidence_handles", "true"),
        ("supporting_evidence_handles", "true"),
        ("all_classification_caps", "true"),
        ("max_claims_inclusive", "1023"),
        ("max_envelope_bytes_inclusive", "4194303"),
        ("max_ttl_seconds_inclusive", "3599"),
        ("strict_case_id", "true"),
        ("lowercase_label", "true"),
        ("s4_frozen_file_count", str(len(S4_FROZEN_SHA256))),
        ("track_b_frozen_artifact_count", str(len(TRACK_B_FROZEN_SHA256))),
        ("s5_test_count", "7"),
        ("s4_test_count", "7"),
        ("s2_regression_test_count", "14"),
        ("bridge_wrapper_present", "true"),
        ("bridge_runtime_caller_present", "false"),
        ("state_store_surface_present", "false"),
        ("mcp_surface_present", "false"),
        ("candidate_evidence_interface_implemented", "true"),
        ("source_artifact_compatibility_binding", "true"),
        ("source_artifact_binding_satisfied", "false"),
        ("track_b_artifact_binding_satisfied", "false"),
        ("track_b_live_binding_satisfied", "false"),
        ("candidate_context_builder_bound", "false"),
        ("truth_manifest_binding_satisfied", "false"),
        ("nonce_single_use_registry_implemented", "false"),
        ("capture_provenance_attested", "false"),
        ("cross_biocortex_opaque_transport_implemented", "false"),
        ("production_profile_active", "false"),
        ("physical_privacy_deletion_resolved", "false"),
        ("authority_policy_custody_resolved", "false"),
        ("real_capture_authorized", "false"),
        ("legacy_live_binding_satisfied_count", "0"),
        ("trial_live_binding_satisfied_count", "0"),
        ("remaining_gap_count", str(len(REMAINING_GAPS))),
        ("remaining_gap_codes", ",".join(REMAINING_GAPS)),
        ("biocortex_runtime_influence", "false"),
        ("performance_claimed", "false"),
        ("side_effects_unlocked", "NONE"),
        ("decision", DECISION),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        rows = check(args.repo.resolve())
    except (CheckFailure, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"S5_CHECK_FAILED\t{error}", file=sys.stderr)
        return 1
    for key, value in rows:
        print(f"{key}\t{value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
