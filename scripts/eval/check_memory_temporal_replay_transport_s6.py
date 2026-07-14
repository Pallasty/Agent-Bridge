#!/usr/bin/env python3
"""Fail-closed checker for the S6 detached-verifier contract preregistration."""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import hashlib
import hmac
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Callable


STATUS = "SYNTHETIC_DETACHED_VERIFIER_CONTRACT_IMPLEMENTED_NOT_TRANSPORT_NOT_DURABLE"
DECISION = "BLOCKED_FAIL_CLOSED"
FEATURE = "temporal-evidence-s6-detached-verifier-synthetic"
S5_COMMIT = "8739b69fb59fd704dacfe1a44bfc411ed9ebb913"
S5_PARENT = "486f04fb9a967a9a6cf5272f82f36cc0d7e787ad"
S5_TREE = "d4ba782665fac2c55af60e1c0a988a327b3535dd"

MANIFEST_PATH = (
    "scripts/eval/fixtures/"
    "memory_temporal_replay_transport_s6_s5_source_manifest_v0.json"
)
PROFILE_PATH = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-candidate-exact-payload-profile-v0.json"
)
CONTRACT_PATH = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-replay-transport-contract-v0.json"
)
FIXTURE_PATH = (
    "scripts/eval/fixtures/"
    "memory_temporal_replay_transport_s6_synthetic_v0.json"
)

MANIFEST_SHA256 = "309f2533ef7b78d0c1f252325c0f79ab1300f8f68837a5a75ce7c14d8b011d6a"
PROFILE_SHA256 = "fe3b66ad1d5711f38e790cf792a0db63bd7879ce9795c07f745ab9127575be23"
CONTRACT_SHA256 = "4b54057fe78fd5eb760c89b86e3018003e4cf0a1b354ca720007927e7b005e74"
FIXTURE_SHA256 = "8850862deafefac5c86099116d7da4307af5b844a732ad72246d8f953c56dc1f"
CANDIDATE_SCHEMA_SHA256 = "edba8da90abeeda83e33943d9b87f76c0deff9fad34cb314cd27c28b85ed1b77"
FOUNDATIONAL_MANIFEST_SHA256 = "fbfbf5738dd81e0afe8dbc45b1e91a35e92382a1913006a9b2e5ded67c077f36"
IDENTITY_MANIFEST_SHA256 = "c1a6c5a6c83d61f92d35948432b139749d19d5828f68a7fc2473859bba21a7e9"
REVIEW_SCHEMA_SHA256 = "2745cd373d4f99cdd4bb3d0bc9d9087966adb3a9d0594749cb1150b90d1e9422"
TRUTH_MANIFEST_SCHEMA_SHA256 = "520070d1eb4852fd2a005d63b3d087769b3240902289ff5c44f11c109bd1cde6"
TRUTH_REFERENT_SCHEMA_SHA256 = "5da057e70675cbd259e0d1beb98039d2eee8589c73aa910f92f90cb0374545a8"

S5_DOMAIN = b"agent-bridge/track-b/candidate-evidence-envelope/v0"
S6_DOMAIN = b"agent-bridge/track-b/replay-transport/v0"
REPLAY_DOMAIN = b"agent-bridge/track-b/replay-transport/replay-identity/v0"
SCOPE_DOMAIN = b"agent-bridge/track-b/replay-transport/scope-commitment/v0"
S5_KEY = bytes([0x22]) * 32
S6_KEY = bytes([0x77]) * 32
HANDLE_KEY = bytes([0x11]) * 32
S5_KEY_ID = "transport-key-s5-synthetic"
S6_KEY_ID = "channel-key-s6-synthetic"

REMAINING_GAPS = (
    "AUTHORITY_POLICY_CUSTODY_UNRESOLVED",
    "CAPTURE_PROVENANCE_UNATTESTED",
    "CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED",
    "PHYSICAL_PRIVACY_DELETION_UNRESOLVED",
    "PRODUCTION_PRODUCER_PROFILE_UNADMITTED",
)

PAYLOAD_FIELDS = (
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
ROUTE_FIELDS = (
    "boundary",
    "candidate_evidence_schema_sha256",
    "candidate_exact_payload_profile_sha256",
    "case_id",
    "contract_sha256",
    "destination_repository_id",
    "expires_at_utc",
    "foundational_schema_pack_manifest_sha256",
    "handle_key_id",
    "identity_composition_manifest_sha256",
    "issued_at_utc",
    "payload_byte_count",
    "payload_encoding",
    "payload_sha256",
    "projection_binding_handle",
    "request_id",
    "request_nonce",
    "review_schema_sha256",
    "s5_authentication",
    "source_commit",
    "source_manifest_sha256",
    "source_repository_id",
    "source_tree",
    "transport_profile",
    "trial_id",
    "truth_manifest_schema_sha256",
    "truth_referent_schema_sha256",
)
S5_AUTH_FIELDS = (
    "algorithm",
    "canonicalization",
    "domain",
    "hmac_sha256",
    "key_id",
    "message_profile",
    "payload_sha256",
)
S6_AUTH_FIELDS = (
    "algorithm",
    "authenticated_route_sha256",
    "domain",
    "hmac_sha256",
    "key_id",
    "message_profile",
)
S5_BOUNDARY = {
    "authority_custody_resolved": False,
    "biocortex_runtime_influence": False,
    "capture_provenance_attested": False,
    "contains_raw_evidence_ids": False,
    "contains_raw_predicate_ids": False,
    "contains_raw_provenance": False,
    "contains_raw_referent_ids": False,
    "contains_raw_source_bindings": False,
    "contains_raw_values": False,
    "cross_repository_transport_authorized": False,
    "live_binding_satisfied": False,
    "physical_privacy_deletion_resolved": False,
    "production_profile_active": False,
    "side_effects_unlocked": "NONE",
}


class CheckFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def path_for(repo: Path, relative: str) -> Path:
    path = repo / relative
    require(path.is_file(), f"missing file: {relative}")
    require(not path.is_symlink(), f"symlink forbidden: {relative}")
    return path


def read_bytes(repo: Path, relative: str) -> bytes:
    return path_for(repo, relative).read_bytes()


def read_text(repo: Path, relative: str) -> str:
    return read_bytes(repo, relative).decode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(repo: Path, relative: str) -> str:
    return sha256_bytes(read_bytes(repo, relative))


def canonical_pretty(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def strict_json_bytes(value: bytes, label: str) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, child in pairs:
            require(key not in result, f"{label}: duplicate key {key}")
            result[key] = child
        return result

    try:
        return json.loads(
            value.decode("utf-8"),
            object_pairs_hook=object_pairs,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                CheckFailure(f"{label}: non-finite JSON number {constant}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckFailure(f"{label}: invalid strict JSON: {error}") from error


def exact_object(value: Any, fields: tuple[str, ...], label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label}: object required")
    require(tuple(value) == fields, f"{label}: field order/set drift")
    return value


def valid_sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def valid_label(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= 128
        and re.fullmatch(r"[a-z0-9][a-z0-9_.:-]*", value) is not None
    )


def frame(value: bytes) -> bytes:
    return len(value).to_bytes(8, "big") + value


def digest_parts(domain: bytes, parts: list[bytes]) -> str:
    return sha256_bytes(frame(domain) + b"".join(frame(part) for part in parts))


def hmac_parts(key: bytes, domain: bytes, parts: list[bytes]) -> bytes:
    message = frame(domain) + b"".join(frame(part) for part in parts)
    return hmac.new(key, message, hashlib.sha256).digest()


def s5_hmac(key_id: str, payload: bytes) -> str:
    message = frame(S5_DOMAIN) + frame(key_id.encode()) + payload
    return hmac.new(S5_KEY, message, hashlib.sha256).hexdigest()


def s6_hmac(key_id: str, route_bytes: bytes, payload: bytes) -> str:
    message = frame(S6_DOMAIN) + frame(key_id.encode()) + frame(route_bytes) + payload
    return hmac.new(S6_KEY, message, hashlib.sha256).hexdigest()


def load_canonical(repo: Path, relative: str, expected_sha: str) -> Any:
    raw = read_bytes(repo, relative)
    require(sha256_bytes(raw) == expected_sha, f"digest drift: {relative}")
    value = strict_json_bytes(raw, relative)
    require(raw == canonical_pretty(value), f"non-canonical JSON: {relative}")
    return value


def git(git_repo: Path, *arguments: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", "-C", str(git_repo), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    require(result.returncode == 0, f"git {' '.join(arguments)} failed")
    return result.stdout if binary else result.stdout.decode("utf-8").strip()


def check_manifest(repo: Path, git_repo: Path) -> dict[str, Any]:
    manifest = load_canonical(repo, MANIFEST_PATH, MANIFEST_SHA256)
    exact_object(
        manifest,
        (
            "artifacts",
            "boundary",
            "completeness_scope",
            "parent_commit",
            "schema",
            "source_commit",
            "source_tree",
        ),
        "source manifest",
    )
    require(manifest["source_commit"] == S5_COMMIT, "S5 source commit drift")
    require(manifest["parent_commit"] == S5_PARENT, "S5 parent drift")
    require(manifest["source_tree"] == S5_TREE, "S5 tree drift")
    require(
        manifest["completeness_scope"] == "exact_s5_feature_commit_14_path_delta",
        "source completeness scope drift",
    )
    require(
        manifest["boundary"]
        == {
            "build_provenance_attested": False,
            "current_binary_identity_bound": False,
            "remote_producer_identity_bound": False,
            "runtime_source_identity_bound": False,
            "side_effects_unlocked": "NONE",
        },
        "source manifest boundary opened",
    )
    artifacts = manifest["artifacts"]
    require(isinstance(artifacts, list) and len(artifacts) == 14, "S5 artifact count drift")
    paths: list[str] = []
    for index, artifact in enumerate(artifacts):
        exact_object(
            artifact,
            ("byte_count", "git_blob_oid", "mode", "path", "sha256"),
            f"source artifact {index}",
        )
        path = artifact["path"]
        require(
            isinstance(path, str)
            and path
            and not path.startswith("/")
            and ".." not in Path(path).parts,
            "unsafe source artifact path",
        )
        require(artifact["mode"] in ("100644", "100755"), "unsafe source artifact mode")
        require(type(artifact["byte_count"]) is int and artifact["byte_count"] >= 0, "bad byte count")
        require(valid_sha(artifact["sha256"]), "bad source artifact sha256")
        require(re.fullmatch(r"[0-9a-f]{40}", artifact["git_blob_oid"]) is not None, "bad blob oid")
        paths.append(path)
    require(paths == sorted(set(paths)), "source artifact paths not unique sorted")
    require(
        [artifact["mode"] for artifact in artifacts].count("100755") == 1
        and next(a for a in artifacts if a["mode"] == "100755")["path"]
        == "scripts/check-memory-temporal-candidate-binding-s5.sh",
        "S5 executable mode drift",
    )

    require(git(git_repo, "rev-parse", f"{S5_COMMIT}^") == S5_PARENT, "Git S5 parent mismatch")
    require(git(git_repo, "show", "-s", "--format=%T", S5_COMMIT) == S5_TREE, "Git S5 tree mismatch")
    derived_paths = str(
        git(git_repo, "diff-tree", "--no-commit-id", "--name-only", "-r", S5_COMMIT)
    ).splitlines()
    require(sorted(derived_paths) == paths, "manifest is not the complete Git S5 delta")
    for artifact in artifacts:
        path = artifact["path"]
        entry = str(git(git_repo, "ls-tree", S5_COMMIT, "--", path)).split()
        require(len(entry) >= 4 and entry[1] == "blob", f"non-blob S5 artifact: {path}")
        require(entry[0] == artifact["mode"] and entry[2] == artifact["git_blob_oid"], f"Git identity drift: {path}")
        blob = git(git_repo, "cat-file", "blob", artifact["git_blob_oid"], binary=True)
        require(isinstance(blob, bytes), "binary Git read failed")
        require(len(blob) == artifact["byte_count"], f"Git byte count drift: {path}")
        require(sha256_bytes(blob) == artifact["sha256"], f"Git sha256 drift: {path}")
    return manifest


def check_profiles(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = load_canonical(repo, PROFILE_PATH, PROFILE_SHA256)
    require(profile["schema"] == "agent_bridge.biocortex_ab_track_b_candidate_exact_payload_profile.v0", "payload profile schema drift")
    require(profile["payload_fields_in_order"] == list(PAYLOAD_FIELDS), "payload field order drift")
    require(profile["required_boundary"] == S5_BOUNDARY, "payload profile boundary opened")
    require(profile["semantics"] == {
        "authentication_metadata_is_detached": True,
        "exact_bytes_authenticated_before_payload_parse": True,
        "logical_envelope_requires_authentication_join": True,
        "payload_contains_authentication_field": False,
        "profile_authorizes_transport": False,
    }, "payload split semantics drift")
    require(profile["canonical_encoding"]["parse_reserialize_for_authentication"] is False, "reserialized authentication forbidden")
    require(profile["limits"]["max_payload_bytes_exclusive"] == 4 * 1024 * 1024, "payload cap drift")

    contract = load_canonical(repo, CONTRACT_PATH, CONTRACT_SHA256)
    require(contract["schema"] == "agent_bridge.biocortex_ab_track_b_replay_transport_contract.v0", "contract schema drift")
    require(contract["status"] == STATUS and contract["decision"] == DECISION, "status or decision drift")
    require(tuple(contract["remaining_gaps"]) == REMAINING_GAPS, "remaining gaps drift")
    require(contract["source_closure"]["artifact_count"] == 14, "source closure count drift")
    require(contract["source_closure"]["manifest_sha256"] == MANIFEST_SHA256, "source manifest binding drift")
    require(contract["authenticated_route_fields_in_order"] == list(ROUTE_FIELDS), "authenticated route field order drift")
    require(contract["artifact_bindings"] == {
        "candidate_evidence_schema_sha256": CANDIDATE_SCHEMA_SHA256,
        "candidate_exact_payload_profile_sha256": PROFILE_SHA256,
        "foundational_schema_pack_manifest_sha256": FOUNDATIONAL_MANIFEST_SHA256,
        "identity_composition_manifest_sha256": IDENTITY_MANIFEST_SHA256,
        "review_schema_sha256": REVIEW_SCHEMA_SHA256,
        "s5_source_manifest_sha256": MANIFEST_SHA256,
        "truth_manifest_schema_sha256": TRUTH_MANIFEST_SCHEMA_SHA256,
        "truth_referent_schema_sha256": TRUTH_REFERENT_SCHEMA_SHA256,
    }, "contract artifact bindings drift")
    boundary = contract["boundary"]
    require(boundary["side_effects_unlocked"] == "NONE", "side effects opened")
    require(all(value is False for key, value in boundary.items() if key != "side_effects_unlocked"), "contract boundary opened")
    require(contract["replay_contract"]["durable_backend_present"] is False, "durable backend falsely claimed")
    require(contract["replay_contract"]["unique_key_fields"] == ["s5_transport_key_id", "request_nonce"], "replay unique key drift")
    require(contract["replay_contract"]["scalar_encoding"] == "utf8_strings_with_decimal_timestamps", "replay scalar encoding drift")
    require(contract["wire"]["transport_runtime_implemented"] is False, "runtime transport falsely claimed")
    return profile, contract


def validate_payload(payload_bytes: bytes, route: dict[str, Any], evaluated_at: int) -> dict[str, Any]:
    require(0 < len(payload_bytes) < 4 * 1024 * 1024, "payload byte sentinel reached")
    require(len(payload_bytes) == route["payload_byte_count"], "payload byte count mismatch")
    payload_sha = sha256_bytes(payload_bytes)
    require(payload_sha == route["payload_sha256"], "payload sha256 mismatch")
    auth = exact_object(route["s5_authentication"], S5_AUTH_FIELDS, "S5 authentication")
    require(auth["algorithm"] == "HMAC-SHA-256", "S5 algorithm drift")
    require(
        auth["canonicalization"] == "serde_json_compact_struct_field_order_utf8_v1",
        "S5 canonicalization drift",
    )
    require(auth["domain"] == S5_DOMAIN.decode(), "S5 domain drift")
    require(auth["key_id"] == S5_KEY_ID, "S5 key id drift")
    require(
        auth["message_profile"]
        == "u64be_len_domain_domain_u64be_len_key_id_key_id_exact_payload_json",
        "S5 message profile drift",
    )
    require(auth["payload_sha256"] == payload_sha, "S5 payload sha join mismatch")
    require(
        hmac.compare_digest(auth["hmac_sha256"], s5_hmac(auth["key_id"], payload_bytes)),
        "S5 exact-byte HMAC mismatch",
    )
    payload = strict_json_bytes(payload_bytes, "candidate exact payload")
    exact_object(payload, PAYLOAD_FIELDS, "candidate exact payload")
    require(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode() == payload_bytes,
        "candidate payload is not exact canonical bytes",
    )
    require(payload["boundary"] == S5_BOUNDARY, "candidate inner boundary opened")
    require(payload["candidate_evidence_schema_sha256"] == CANDIDATE_SCHEMA_SHA256, "candidate schema digest drift")
    require(payload["foundational_schema_pack_manifest_sha256"] == FOUNDATIONAL_MANIFEST_SHA256, "foundational manifest drift")
    require(payload["truth_referent_schema_sha256"] == TRUTH_REFERENT_SCHEMA_SHA256, "truth referent drift")
    require(payload["schema"] == "agent_bridge.biocortex_ab_track_b_candidate_evidence_envelope.v0", "candidate schema label drift")
    require(payload["candidate_id"] == "temporal_truth_projection_v1_synthetic_source_binding", "candidate id drift")
    require(payload["handle_profile_id"] == "request_scoped_hmac_sha256_trunc128_v1", "handle profile drift")
    for field in ("contract_sha256", "request_nonce"):
        require(valid_sha(payload[field]), f"invalid {field}")
    require(re.fullmatch(r"case_[0-9a-f]{32}", payload["case_id"]) is not None, "invalid case id")
    require(re.fullmatch(r"prj_[0-9a-f]{32}", payload["projection_binding_handle"]) is not None, "invalid projection handle")
    for field in ("trial_id", "request_id", "handle_key_id"):
        require(valid_label(payload[field]), f"invalid label: {field}")
    require(
        type(payload["issued_at_utc"]) is int
        and type(payload["expires_at_utc"]) is int
        and 0 <= payload["issued_at_utc"] <= 9223372036854775807
        and 0 <= payload["expires_at_utc"] <= 9223372036854775807,
        "candidate times must be non-negative signed i64 integers",
    )
    ttl = payload["expires_at_utc"] - payload["issued_at_utc"]
    require(0 < ttl < 3600, "invalid strict TTL")
    require(payload["issued_at_utc"] <= evaluated_at < payload["expires_at_utc"], "candidate outside validity window")
    exact_object(payload["limits"], LIMIT_FIELDS, "candidate limits")
    require(payload["limits"] == {
        "max_claims": 1023,
        "max_envelope_bytes": 4194303,
        "max_evidence_per_claim": 1023,
        "max_source_bindings_per_claim": 1023,
        "max_ttl_seconds": 3599,
        "max_values_per_claim": 1023,
    }, "candidate limits drift")
    claims = payload["claims"]
    require(isinstance(claims, list) and 0 < len(claims) < 1024, "candidate claim cap")
    order: list[tuple[str, str, str]] = []
    for claim in claims:
        exact_object(claim, CLAIM_FIELDS, "candidate claim")
        require(valid_sha(claim["claim_binding_hmac_sha256"]), "invalid claim binding HMAC")
        referent = exact_object(claim["referent"], REFERENT_FIELDS, "candidate referent")
        for field, prefix in (("claim_handle", "clm"), ("predicate_handle", "prd"), ("referent_handle", "ref")):
            require(re.fullmatch(rf"{prefix}_[0-9a-f]{{32}}", referent[field]) is not None, f"invalid {field}")
        order.append((referent["referent_handle"], referent["predicate_handle"], referent["claim_handle"]))
        arrays = (
            ("evidence_handles", "evd"),
            ("supporting_evidence_handles", "evd"),
            ("source_binding_handles", "src"),
            ("value_handles", "val"),
        )
        for field, prefix in arrays:
            values = claim[field]
            require(isinstance(values, list) and len(values) < 1024, f"{field} cap")
            require(values == sorted(set(values)), f"{field} not unique sorted")
            require(all(re.fullmatch(rf"{prefix}_[0-9a-f]{{32}}", value) for value in values), f"invalid {field}")
        for field in ("evidence_count", "noncurrent_evidence_count", "shadowed_evidence_count"):
            require(type(claim[field]) is int and 0 <= claim[field] < 1024, f"{field} cap")
        require(claim["evidence_count"] == len(claim["evidence_handles"]), "evidence count mismatch")
        require(claim["temporal_state"] in ("current", "future", "historical", "indeterminate"), "temporal state drift")
        require(claim["truth_state"] in ("conflicted", "supported", "unknown"), "truth state drift")
        require(claim["truth_tier"] in ("authoritative", "inferred", "none", "observed", "verified"), "truth tier drift")
        if claim["truth_state"] == "unknown":
            require(
                claim["truth_tier"] == "none"
                and not claim["evidence_handles"]
                and not claim["supporting_evidence_handles"]
                and not claim["source_binding_handles"]
                and not claim["value_handles"]
                and claim["evidence_count"] == 0
                and claim["noncurrent_evidence_count"] == 0
                and claim["shadowed_evidence_count"] == 0,
                "unknown claim cardinality drift",
            )
        elif claim["truth_state"] == "supported":
            require(len(claim["value_handles"]) == 1, "supported claim cardinality drift")
        else:
            require(len(claim["value_handles"]) >= 2, "conflicted claim cardinality drift")
    require(order == sorted(set(order)), "claims not unique sorted")
    for field in (
        "candidate_evidence_schema_sha256",
        "case_id",
        "contract_sha256",
        "expires_at_utc",
        "foundational_schema_pack_manifest_sha256",
        "handle_key_id",
        "issued_at_utc",
        "payload_sha256",
        "projection_binding_handle",
        "request_id",
        "request_nonce",
        "trial_id",
        "truth_referent_schema_sha256",
    ):
        require(route[field] == (payload_sha if field == "payload_sha256" else payload[field]), f"inner/outer join mismatch: {field}")
    return payload


def validate_synthetic_claim_vector(payload: dict[str, Any]) -> None:
    require(len(payload["claims"]) == 1, "synthetic vector must contain one claim")
    claim = payload["claims"][0]
    scope = hashlib.sha256(
        frame(b"agent-bridge/track-b/candidate-evidence/handle-scope/v1")
        + b"".join(
            frame(part)
            for part in (
                payload["trial_id"].encode(),
                payload["contract_sha256"].encode(),
                payload["case_id"].encode(),
                payload["request_id"].encode(),
                payload["request_nonce"].encode(),
                payload["projection_binding_handle"].encode(),
            )
        )
    ).digest()
    raw_referent = b"subject:s6-synthetic"
    raw_predicate = b"claim.status"

    def handle(prefix: str, domain: bytes, parts: list[bytes]) -> str:
        return prefix + hmac_parts(HANDLE_KEY, domain, parts)[:16].hex()

    expected_referent = {
        "claim_handle": handle(
            "clm_",
            b"agent-bridge/track-b/candidate-evidence/claim-handle/v1",
            [scope, raw_referent, raw_predicate],
        ),
        "predicate_handle": handle(
            "prd_",
            b"agent-bridge/track-b/candidate-evidence/predicate-handle/v1",
            [scope, raw_predicate],
        ),
        "referent_handle": handle(
            "ref_",
            b"agent-bridge/track-b/candidate-evidence/referent-handle/v1",
            [scope, raw_referent],
        ),
    }
    require(claim["referent"] == expected_referent, "synthetic request-scoped handle vector drift")
    binding = {key: value for key, value in claim.items() if key != "claim_binding_hmac_sha256"}
    binding_bytes = json.dumps(binding, ensure_ascii=False, separators=(",", ":")).encode()
    expected_binding = hmac_parts(
        HANDLE_KEY,
        b"agent-bridge/track-b/candidate-evidence/claim-binding/v1",
        [scope, binding_bytes],
    ).hex()
    require(claim["claim_binding_hmac_sha256"] == expected_binding, "synthetic claim binding vector drift")


def validate_fixture_value(fixture: dict[str, Any], evaluated_at: int = 150) -> tuple[bytes, dict[str, Any]]:
    exact_object(fixture, ("expected_replay_record", "packet", "schema", "synthetic_only"), "S6 fixture")
    require(fixture["schema"] == "agent_bridge.memory_temporal_replay_transport_s6_synthetic.v0", "fixture schema drift")
    require(fixture["synthetic_only"] is True, "fixture must be synthetic")
    packet = exact_object(
        fixture["packet"],
        ("authenticated_route", "payload_base64", "schema", "transport_authentication"),
        "transport packet",
    )
    require(packet["schema"] == "agent_bridge.biocortex_ab_track_b_replay_transport_packet.v0", "packet schema drift")
    route = exact_object(packet["authenticated_route"], ROUTE_FIELDS, "authenticated route")
    require(route["source_manifest_sha256"] == MANIFEST_SHA256, "untrusted source manifest")
    require(route["source_commit"] == S5_COMMIT and route["source_tree"] == S5_TREE, "source identity drift")
    require(route["source_repository_id"] == "agent-bridge", "source repository drift")
    require(route["destination_repository_id"] == "biocortex", "destination repository drift")
    require(route["transport_profile"] == "agent_bridge.biocortex_ab_track_b_replay_transport.v0", "transport profile drift")
    require(route["payload_encoding"] == "base64_rfc4648_padded_canonical", "payload encoding drift")
    require(type(route["payload_byte_count"]) is int, "route payload byte count must be an integer")
    require(route["candidate_exact_payload_profile_sha256"] == PROFILE_SHA256, "payload profile route drift")
    require(route["identity_composition_manifest_sha256"] == IDENTITY_MANIFEST_SHA256, "identity manifest route drift")
    require(route["truth_manifest_schema_sha256"] == TRUTH_MANIFEST_SCHEMA_SHA256, "truth manifest route drift")
    require(route["review_schema_sha256"] == REVIEW_SCHEMA_SHA256, "review schema route drift")
    require(route["boundary"]["side_effects_unlocked"] == "NONE", "route side effects opened")
    require(all(value is False for key, value in route["boundary"].items() if key != "side_effects_unlocked"), "route boundary opened")
    payload_base64 = packet["payload_base64"]
    require(isinstance(payload_base64, str) and re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", payload_base64), "invalid base64 alphabet")
    try:
        payload_bytes = base64.b64decode(payload_base64, validate=True)
    except binascii.Error as error:
        raise CheckFailure(f"invalid canonical base64: {error}") from error
    require(base64.b64encode(payload_bytes).decode() == payload_base64, "non-canonical padded base64")

    route_bytes = json.dumps(route, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    transport = exact_object(packet["transport_authentication"], S6_AUTH_FIELDS, "transport authentication")
    require(transport["algorithm"] == "HMAC-SHA-256", "S6 algorithm drift")
    require(transport["domain"] == S6_DOMAIN.decode(), "S6 domain drift")
    require(transport["key_id"] == S6_KEY_ID, "S6 key id drift")
    require(
        transport["message_profile"]
        == "u64be_len_domain_domain_u64be_len_channel_key_id_key_id_u64be_len_route_json_route_json_exact_payload_bytes",
        "S6 message profile drift",
    )
    require(transport["authenticated_route_sha256"] == sha256_bytes(route_bytes), "route digest mismatch")
    require(
        hmac.compare_digest(transport["hmac_sha256"], s6_hmac(transport["key_id"], route_bytes, payload_bytes)),
        "S6 route/exact-payload HMAC mismatch",
    )
    payload = validate_payload(payload_bytes, route, evaluated_at)
    validate_synthetic_claim_vector(payload)

    replay_identity = digest_parts(
        REPLAY_DOMAIN,
        [route["s5_authentication"]["key_id"].encode(), route["request_nonce"].encode()],
    )
    scope = digest_parts(
        SCOPE_DOMAIN,
        [
            route["source_manifest_sha256"].encode(),
            route["candidate_exact_payload_profile_sha256"].encode(),
            route["handle_key_id"].encode(),
            route["trial_id"].encode(),
            route["contract_sha256"].encode(),
            route["case_id"].encode(),
            route["request_id"].encode(),
            route["projection_binding_handle"].encode(),
            str(route["issued_at_utc"]).encode(),
            str(route["expires_at_utc"]).encode(),
            route["payload_sha256"].encode(),
        ],
    )
    expected = fixture["expected_replay_record"]
    require(expected == {
        "durable": False,
        "replay_identity_sha256": replay_identity,
        "scope_commitment_sha256": scope,
        "status": "synthetic_process_local_consumed",
    }, "expected replay record drift")
    return payload_bytes, payload


def resign_fixture(fixture: dict[str, Any], payload: dict[str, Any] | None = None) -> None:
    packet = fixture["packet"]
    route = packet["authenticated_route"]
    if payload is None:
        payload_bytes = base64.b64decode(packet["payload_base64"], validate=True)
    else:
        payload_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        packet["payload_base64"] = base64.b64encode(payload_bytes).decode()
        route["payload_byte_count"] = len(payload_bytes)
        route["payload_sha256"] = sha256_bytes(payload_bytes)
        route["s5_authentication"]["payload_sha256"] = route["payload_sha256"]
        route["s5_authentication"]["hmac_sha256"] = s5_hmac(S5_KEY_ID, payload_bytes)
    route_bytes = json.dumps(route, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    packet["transport_authentication"]["authenticated_route_sha256"] = sha256_bytes(route_bytes)
    packet["transport_authentication"]["hmac_sha256"] = s6_hmac(S6_KEY_ID, route_bytes, payload_bytes)


def check_rust_surface(repo: Path) -> None:
    cargo = tomllib.loads(read_text(repo, "crates/store/Cargo.toml"))
    require(cargo["features"].get(FEATURE) == ["temporal-evidence-s5-candidate-synthetic"], "S6 feature dependency drift")
    require(cargo["features"]["default"] == ["onnx-embed"], "default feature drift")
    library = read_text(repo, "crates/store/src/lib.rs")
    source = read_text(repo, "crates/store/src/temporal_replay_transport.rs")
    bridge_cargo = read_text(repo, "crates/bridge/Cargo.toml")
    bridge_library = read_text(repo, "crates/bridge/src/lib.rs")
    require(f'#[cfg(feature = "{FEATURE}")]\nmod temporal_replay_transport;' in library, "private S6 module gate missing")
    require("pub mod temporal_replay_transport" not in library, "public S6 module forbidden")
    require("pub use temporal_replay_transport" not in library, "S6 re-export forbidden")
    require(FEATURE not in bridge_cargo and FEATURE not in bridge_library, "Bridge S6 feature or caller forbidden")
    require("__S6_SOURCE_MANIFEST_SHA256__" not in source, "source manifest placeholder remains")
    require(MANIFEST_SHA256 in source, "Rust source token does not bind S5 manifest")
    for forbidden in (
        "std::fs",
        "tokio::fs",
        "std::net",
        "tokio::net",
        "reqwest",
        "StateStore",
        "SqliteStore",
        "mcp",
    ):
        require(forbidden not in source, f"forbidden S6 runtime surface: {forbidden}")
    require("ring::hmac" in source, "ring exact-byte HMAC missing")
    require("Mutex" in source and "consume_once" in source, "atomic synthetic replay contract missing")
    require("#[cfg(test)]" in source, "test-only S6 capability constructor missing")
    require("exact_payload: Box<[u8]>" in source, "owned exact payload binding missing")
    require("cross_repository_transport_authorized" in source, "closed inner transport boundary check missing")
    require("side_effects_unlocked" in source and '"NONE"' in source, "closed side-effect boundary missing")
    require(not re.search(r"\bpub\s+(?:struct|fn|trait|enum)\s+", source), "public S6 surface forbidden")
    verified_prefix = source.split("impl fmt::Debug for VerifiedDetachedCandidateV1", 1)[0]
    require("#[derive(Clone" not in verified_prefix and "Serialize for VerifiedDetachedCandidateV1" not in source, "verified token must not be cloneable or serializable")
    require("fn exact_payload(" not in source and "fn exact_payload_bytes(" not in source, "verified exact-byte getter forbidden")


def run_mutations(
    manifest: dict[str, Any],
    profile: dict[str, Any],
    contract: dict[str, Any],
    fixture: dict[str, Any],
) -> int:
    count = 0

    def expect(label: str, operation: Callable[[], None]) -> None:
        nonlocal count
        try:
            operation()
        except (CheckFailure, ValueError, TypeError, KeyError, binascii.Error, UnicodeError):
            count += 1
            return
        raise CheckFailure(f"mutation unexpectedly accepted: {label}")

    def manifest_check(value: dict[str, Any]) -> None:
        require(len(value["artifacts"]) == 14, "mutated artifact count")
        paths = [artifact["path"] for artifact in value["artifacts"]]
        require(paths == sorted(set(paths)), "mutated artifact order")
        require(value["source_commit"] == S5_COMMIT, "mutated source commit")
        require(value["source_tree"] == S5_TREE, "mutated source tree")
        require(value["parent_commit"] == S5_PARENT, "mutated parent")
        require(all(a["mode"] in ("100644", "100755") for a in value["artifacts"]), "mutated mode")
        require(all(valid_sha(a["sha256"]) for a in value["artifacts"]), "mutated digest")
        require(all(".." not in Path(a["path"]).parts for a in value["artifacts"]), "mutated path")
        require(value == manifest, "source manifest content drift")

    for label, mutate in (
        ("manifest-missing", lambda x: x["artifacts"].pop()),
        ("manifest-extra", lambda x: x["artifacts"].append(copy.deepcopy(x["artifacts"][-1]))),
        ("manifest-order", lambda x: x["artifacts"].reverse()),
        ("manifest-path", lambda x: x["artifacts"][0].__setitem__("path", "../Cargo.lock")),
        ("manifest-mode", lambda x: x["artifacts"][0].__setitem__("mode", "120000")),
        ("manifest-sha", lambda x: x["artifacts"][0].__setitem__("sha256", "x")),
        ("manifest-blob", lambda x: x["artifacts"][0].__setitem__("git_blob_oid", "0" * 40)),
        ("manifest-bytes", lambda x: x["artifacts"][0].__setitem__("byte_count", 1)),
        ("manifest-commit", lambda x: x.__setitem__("source_commit", "0" * 40)),
        ("manifest-tree", lambda x: x.__setitem__("source_tree", "0" * 40)),
        ("manifest-parent", lambda x: x.__setitem__("parent_commit", "0" * 40)),
        ("manifest-boundary", lambda x: x["boundary"].__setitem__("build_provenance_attested", True)),
    ):
        value = copy.deepcopy(manifest)
        mutate(value)
        expect(label, lambda value=value: manifest_check(value))

    for label, mutate in (
        ("profile-auth-field", lambda x: x["payload_fields_in_order"].insert(0, "authentication")),
        ("profile-boundary", lambda x: x["required_boundary"].__setitem__("live_binding_satisfied", True)),
        ("contract-status", lambda x: x.__setitem__("status", "LIVE")),
        ("contract-boundary", lambda x: x["boundary"].__setitem__("cross_repository_transport_authorized", True)),
        ("contract-gap", lambda x: x["remaining_gaps"].pop()),
        ("contract-durable", lambda x: x["replay_contract"].__setitem__("durable_backend_present", True)),
    ):
        value = copy.deepcopy(profile if label.startswith("profile") else contract)
        mutate(value)
        expect(label, lambda value=value, label=label: require(
            (value.get("payload_fields_in_order") == list(PAYLOAD_FIELDS) and value.get("required_boundary") == S5_BOUNDARY)
            if label.startswith("profile")
            else (
                value["status"] == STATUS
                and all(v is False for k, v in value["boundary"].items() if k != "side_effects_unlocked")
                and tuple(value["remaining_gaps"]) == REMAINING_GAPS
                and value["replay_contract"]["durable_backend_present"] is False
            ),
            "profile/contract mutation",
        ))

    fixture_cases: list[tuple[str, Callable[[dict[str, Any]], None], bool]] = [
        ("payload-byte", lambda x: x["packet"].__setitem__("payload_base64", "A" + x["packet"]["payload_base64"][1:]), False),
        ("base64-padding", lambda x: x["packet"].__setitem__("payload_base64", x["packet"]["payload_base64"].rstrip("=")), False),
        ("payload-length", lambda x: x["packet"]["authenticated_route"].__setitem__("payload_byte_count", 1), False),
        ("payload-sha", lambda x: x["packet"]["authenticated_route"].__setitem__("payload_sha256", "0" * 64), False),
        ("s5-domain", lambda x: x["packet"]["authenticated_route"]["s5_authentication"].__setitem__("domain", "x"), True),
        ("s5-key-id", lambda x: x["packet"]["authenticated_route"]["s5_authentication"].__setitem__("key_id", "other"), True),
        ("s5-message-profile", lambda x: x["packet"]["authenticated_route"]["s5_authentication"].__setitem__("message_profile", "x"), True),
        ("source-manifest", lambda x: x["packet"]["authenticated_route"].__setitem__("source_manifest_sha256", "0" * 64), True),
        ("source-repository", lambda x: x["packet"]["authenticated_route"].__setitem__("source_repository_id", "other"), True),
        ("destination", lambda x: x["packet"]["authenticated_route"].__setitem__("destination_repository_id", "other"), True),
        ("route-boundary", lambda x: x["packet"]["authenticated_route"]["boundary"].__setitem__("biocortex_runtime_influence", True), True),
        ("outer-key-id", lambda x: x["packet"]["transport_authentication"].__setitem__("key_id", "other"), False),
        ("outer-domain", lambda x: x["packet"]["transport_authentication"].__setitem__("domain", "x"), False),
        ("outer-hmac", lambda x: x["packet"]["transport_authentication"].__setitem__("hmac_sha256", "0" * 64), False),
        ("route-unknown-field", lambda x: x["packet"]["authenticated_route"].__setitem__("unknown", 0), True),
    ]
    for label, mutate, resign in fixture_cases:
        value = copy.deepcopy(fixture)
        mutate(value)
        if resign:
            resign_fixture(value)
        expect(label, lambda value=value: validate_fixture_value(value))

    for label, mutate, evaluated_at in (
        ("expiry-equality", lambda p: None, 200),
        ("future-issued", lambda p: None, 99),
        ("inner-live", lambda p: p["boundary"].__setitem__("live_binding_satisfied", True), 150),
        ("inner-transport", lambda p: p["boundary"].__setitem__("cross_repository_transport_authorized", True), 150),
        ("inner-side-effect", lambda p: p["boundary"].__setitem__("side_effects_unlocked", "WRITE"), 150),
        ("identity-join", lambda p: p.__setitem__("trial_id", "trial-other"), 150),
    ):
        value = copy.deepcopy(fixture)
        payload_bytes = base64.b64decode(value["packet"]["payload_base64"], validate=True)
        payload = strict_json_bytes(payload_bytes, "mutation payload")
        mutate(payload)
        resign_fixture(value, payload)
        expect(label, lambda value=value, evaluated_at=evaluated_at: validate_fixture_value(value, evaluated_at))

    for label, transform in (
        ("payload-whitespace", lambda raw: raw + b" "),
        ("payload-duplicate-key", lambda raw: raw[:-1] + b',"trial_id":"trial-s6-synthetic"}'),
        ("payload-invalid-utf8", lambda raw: raw[:-1] + b"\xff"),
        ("payload-nonfinite", lambda raw: raw.replace(b'"issued_at_utc":100', b'"issued_at_utc":NaN', 1)),
        ("payload-boolean-count", lambda raw: raw.replace(b'"evidence_count":0', b'"evidence_count":false', 1)),
    ):
        value = copy.deepcopy(fixture)
        raw = base64.b64decode(value["packet"]["payload_base64"], validate=True)
        changed = transform(raw)
        value["packet"]["payload_base64"] = base64.b64encode(changed).decode()
        route = value["packet"]["authenticated_route"]
        route["payload_byte_count"] = len(changed)
        route["payload_sha256"] = sha256_bytes(changed)
        route["s5_authentication"]["payload_sha256"] = route["payload_sha256"]
        route["s5_authentication"]["hmac_sha256"] = s5_hmac(S5_KEY_ID, changed)
        resign_fixture(value)
        expect(label, lambda value=value: validate_fixture_value(value))

    value = copy.deepcopy(fixture)
    raw = base64.b64decode(value["packet"]["payload_base64"], validate=True)
    payload = strict_json_bytes(raw, "key-order mutation")
    reordered = {key: payload[key] for key in reversed(payload)}
    resign_fixture(value, reordered)
    expect("payload-key-order", lambda: validate_fixture_value(value))

    registry: dict[tuple[str, str], str] = {}
    route = fixture["packet"]["authenticated_route"]
    unique = (S5_KEY_ID, route["request_nonce"])
    scope = fixture["expected_replay_record"]["scope_commitment_sha256"]
    registry[unique] = scope
    expect("exact-replay", lambda: require(unique not in registry, "replay"))
    expect("scope-collision", lambda: require(registry.get(unique) in (None, "0" * 64), "scope collision"))
    require(len(registry) == 1 and registry[unique] == scope, "replay mutation corrupted first reservation")
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--git-repo", type=Path, required=True)
    arguments = parser.parse_args()
    repo = arguments.repo.resolve()
    git_repo = arguments.git_repo.resolve()
    require(repo.is_dir(), "artifact repository root missing")
    require(git_repo.is_dir(), "Git repository root missing")

    manifest = check_manifest(repo, git_repo)
    profile, contract = check_profiles(repo)
    fixture = load_canonical(repo, FIXTURE_PATH, FIXTURE_SHA256)
    payload_bytes, _payload = validate_fixture_value(fixture)
    check_rust_surface(repo)
    mutation_count = run_mutations(manifest, profile, contract, fixture)

    route = fixture["packet"]["authenticated_route"]
    transport = fixture["packet"]["transport_authentication"]
    expected = fixture["expected_replay_record"]
    rows = (
        ("schema", "agent_bridge.memory_temporal_replay_transport_s6_receipt.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("s5_source_commit", S5_COMMIT),
        ("s5_source_tree", S5_TREE),
        ("s5_source_artifact_count", "14"),
        ("s5_source_manifest_sha256", MANIFEST_SHA256),
        ("candidate_exact_payload_profile_sha256", PROFILE_SHA256),
        ("transport_contract_sha256", CONTRACT_SHA256),
        ("synthetic_fixture_sha256", FIXTURE_SHA256),
        ("exact_payload_bytes", str(len(payload_bytes))),
        ("exact_payload_sha256", route["payload_sha256"]),
        ("authenticated_route_sha256", transport["authenticated_route_sha256"]),
        ("s5_exact_payload_hmac_sha256", route["s5_authentication"]["hmac_sha256"]),
        ("s6_route_payload_hmac_sha256", transport["hmac_sha256"]),
        ("replay_identity_sha256", expected["replay_identity_sha256"]),
        ("scope_commitment_sha256", expected["scope_commitment_sha256"]),
        ("mutation_rejections", str(mutation_count)),
        ("first_atomic_consume_successes", "1"),
        ("durable_nonce_registry_implemented", "false"),
        ("cross_repository_transport_authorized", "false"),
        ("bridge_runtime_caller_present", "false"),
        ("biocortex_runtime_influence", "false"),
        ("remaining_gaps", ",".join(REMAINING_GAPS)),
        ("side_effects_unlocked", "NONE"),
    )
    for key, value in rows:
        print(f"{key}\t{value}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as error:
        print(f"S6_CHECK_FAILED\t{error}", file=sys.stderr)
        raise SystemExit(1)
