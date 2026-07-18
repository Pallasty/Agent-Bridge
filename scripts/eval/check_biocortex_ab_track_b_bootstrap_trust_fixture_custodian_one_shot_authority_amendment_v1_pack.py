#!/usr/bin/env python3
"""Independent checker for the one-shot fixture-custodian amendment pack."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
STEM = "biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1"
SOURCE = ROOT / "scripts/eval" / f"{STEM}.py"
FIXTURE = ROOT / "scripts/eval/fixtures" / f"{STEM}_owner_decision_v0.json"
EXPECTED = ROOT / "scripts/eval/fixtures" / f"{STEM}_pack.expected.v0.tsv"
MANIFEST = ROOT / "scripts/eval/fixtures" / f"{STEM}_pack_v0.json"
FRAME_FIXTURE = ROOT / "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_synthetic_v0.json"
SCHEMA = "agent_bridge.biocortex_ab_track_b.bootstrap_trust_fixture_custodian_one_shot_authority_amendment.v1"
EVENT = "FIXTURE_CUSTODIAN_PROCESS_STARTED_BEFORE_RANDOMNESS_OR_KEYGEN"
EXPECTED_RECORD_RAW_SHA256 = "d913fa29cdef6d9ebf7ffa3a07c5cd687eaf26cd57611d255776016b8683076f"
EXPECTED_RECORD_CANONICAL_SHA256 = "ee0c4ab2f12d3c540a72c2e8af37e4d9705ac4861c4368834e2bdb518356f21b"


class CheckFailed(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise CheckFailed(reason)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CheckFailed("duplicate JSON key")
        result[key] = value
    return result


def load_json_bytes(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckFailed("invalid JSON") from exc


def validate_record(record: Any) -> None:
    require(isinstance(record, dict), "record object")
    require(canonical_sha256(record) == EXPECTED_RECORD_CANONICAL_SHA256, "complete record oracle")
    require(record.get("schema") == SCHEMA and type(record.get("schema_version")) is int and record.get("schema_version") == 1, "schema")
    require(record.get("date") == "2026-07-17", "date")
    provenance = record.get("decision_provenance", {})
    require(provenance.get("directive_observed_in_owner_session") is True, "directive")
    require(provenance.get("explicit_fixture_generation_authority_observed") is True, "owner authority")
    require(provenance.get("explicit_production_authority_observed") is False, "production authority")

    predecessor = record.get("predecessor", {})
    require(predecessor.get("authority_integration_commit") == "a18f0af7b4cbaa971143c71080a2b49786a7f7a3", "predecessor commit")
    require(predecessor.get("authority_integration_tree") == "8afca41122ee482493afec9c2c4aa32d600c175e", "predecessor tree")
    require(predecessor.get("authority_effective") is True, "predecessor effective")
    require(predecessor.get("authority_single_use_consumed") is False, "implementation authority consumption")
    hashes = predecessor.get("authority_artifact_raw_sha256")
    require(isinstance(hashes, dict) and len(hashes) == 7, "authority artifacts")
    require(all(isinstance(value, str) and len(value) == 64 for value in hashes.values()), "authority hashes")

    semantic = record.get("semantic_amendment", {})
    chain = semantic.get("trust_chain_semantics", {})
    require(chain.get("exact_chain_entry_count") == 3, "chain entries")
    require(chain.get("certificate_link_signature_count") == 0, "chain signatures")
    require(chain.get("cryptographic_verification_count_on_positive_path") == 1, "positive verifies")
    require(chain.get("pki_path_validation_claimed") is False, "pki claim")
    role = semantic.get("declared_role_mapping", {})
    require(role.get("generic_declared_role_class") == "SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY", "generic role")
    require(role.get("mapping_is_role_scope_authorization") is False, "role authorization")
    require(role.get("track_role_map") == {
        "MANAGED_SPANNER_CLOUD_KMS": "KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER",
        "SELF_HOSTED_ETCD_OPENBAO": "KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER",
    }, "role map")

    authority = record.get("fixture_custodian_authority", {})
    expected_authority = {
        "authority_effective_only_after_integrated_full_gate": True,
        "authority_single_use_consumed": False,
        "consumption_event": EVENT,
        "exact_keypair_generation_count": 6,
        "exact_signature_generation_count": 2,
        "revoked_leaf_keypair_generation_count": 0,
        "revoked_leaf_signature_generation_count": 0,
        "retry_authorized": False,
        "network_allowed": False,
        "credential_authority": False,
        "provider_authority": False,
        "production_root_or_key_material_allowed": False,
        "effective_external_paid_spend_cap": 0,
        "generator_source_or_executable_may_be_committed": False,
        "ephemeral_generator_executable_mode": "0700",
        "local_os_csprng_allowed": True,
        "private_memory_zeroization_proved": False,
        "swap_exclusion_proved": False,
        "max_parallel_workers": 1,
        "max_private_scratch_bytes": 67108864,
        "scratch_directory_mode": "0700",
        "scratch_non_executable_file_mode": "0600",
    }
    for key, value in expected_authority.items():
        actual = authority.get(key)
        require(type(actual) is type(value) and actual == value, f"authority {key}")
    require(authority.get("allowed_dependency") == {
        "cargo_net_offline_required": True,
        "crate": "ring",
        "repository_cargo_files_may_change": False,
        "version": "0.17.14",
    }, "dependency")

    output = record.get("output_contract", {})
    require(type(output.get("public_key_count")) is int and output.get("public_key_count") == 6, "public key count")
    require(type(output.get("signature_count")) is int and output.get("signature_count") == 2, "signature count")
    require(type(output.get("vector_bundle_track_count")) is int and output.get("vector_bundle_track_count") == 2, "track count")
    receipt_fields = output.get("generation_receipt_required_fields", [])
    require(isinstance(receipt_fields, list) and len(receipt_fields) == 24 and len(set(receipt_fields)) == 24, "receipt fields")
    require(output.get("generation_receipt_serialization") == "SORTED_KEYS_COMPACT_UTF8_SINGLE_TRAILING_LF", "receipt serialization")
    serialization = output.get("vector_bundle_serialization", {})
    require(serialization.get("canonical_json_profile") == "SORTED_KEYS_COMPACT_UTF8_SINGLE_TRAILING_LF", "vector serialization")
    require(serialization.get("public_key_hex_pattern") == "^[0-9a-f]{64}$", "public key encoding")
    require(serialization.get("signature_hex_pattern") == "^[0-9a-f]{128}$", "signature encoding")
    separation = record.get("separation_of_duties", {})
    require(separation.get("minimum_distinct_semantic_actor_count") == 4, "actor count")
    require(separation.get("pairwise_distinct_required") is True, "actor distinctness")

    vector = record.get("synthetic_vector_contract", {})
    require(vector.get("algorithm") == "ED25519", "algorithm")
    require(vector.get("signature_scheme") == "ED25519_PURE_RFC8032_NO_CONTEXT_NO_PREHASH", "signature scheme")
    tracks = vector.get("tracks")
    require(isinstance(tracks, list) and len(tracks) == 2, "tracks")
    expected_tracks = [
        ("MANAGED_SPANNER_CLOUD_KMS", 659, "e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295", 79, 754, "a52aa400add05bb7b545c9eddbf1f48e55befd393f07c5c6ba6baaefd4f5343b"),
        ("SELF_HOSTED_ETCD_OPENBAO", 658, "da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e", 83, 757, "2eb3584afe6c8f18281224785ec083e531da37eed71524f2eedbf3a8225055ac"),
    ]
    for track, frozen in zip(tracks, expected_tracks, strict=True):
        require(isinstance(track, dict), "track object")
        keys = ("track_id", "canonical_frame_bytes", "canonical_frame_sha256", "domain_bytes", "constructed_message_bytes", "constructed_message_sha256")
        require(tuple(track.get(key) for key in keys) == frozen, "track message anchor")
        require(track.get("revoked_leaf_key_generation_authorized") is False, "revoked leaf keygen")

    state = record.get("state_machine", {})
    require(state.get("current_state") == "AUTHORIZED_PENDING_INTEGRATED_FULL_GATE", "pending state")
    require(state.get("states") == [
        "UNRECORDED_NO_AUTHORITY",
        "AUTHORIZED_PENDING_INTEGRATED_FULL_GATE",
        "AUTHORIZED_ONE_SHOT_FIXTURE_CUSTODIAN_PENDING_PROCESS_START",
        "CONSUMED_PROCESS_STARTED_OUTPUT_PENDING",
        "CONSUMED_SCOPE_COMPLETE_PUBLIC_OUTPUT_AVAILABLE",
        "CONSUMED_FAILED_NO_RETRY_REQUIRES_NEW_OWNER_DECISION",
        "INVALIDATED_REQUIRES_NEW_DECISION",
    ], "state catalog")
    transitions = state.get("transitions", [])
    require(sum(item.get("event") == EVENT for item in transitions if isinstance(item, dict)) == 1, "consumption event")
    require(record.get("nonclaims", {}).get("global_single_use_proved") is False, "single-use claim")
    require(record.get("boundary", {}).get("bootstrap_trust_verifier_implementation_authority_single_use_consumed") is False, "implementation consumption boundary")


def reconstruct_frozen_messages(record: dict[str, Any]) -> int:
    require(sha256_path(FRAME_FIXTURE) == "324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9", "frame fixture hash")
    frame_packet = load_json_bytes(FRAME_FIXTURE.read_bytes())
    require(isinstance(frame_packet, dict), "frame packet")
    valid_frames = frame_packet.get("valid_frames")
    require(isinstance(valid_frames, list) and len(valid_frames) == 2, "frame cardinality")
    frames: dict[str, bytes] = {}
    for item in valid_frames:
        require(isinstance(item, dict) and set(item) == {"track_id", "frame_utf8"}, "frame fields")
        track_id = item["track_id"]
        require(track_id not in frames and isinstance(item["frame_utf8"], str), "frame uniqueness")
        frames[track_id] = item["frame_utf8"].encode("utf-8")
    vector = record["synthetic_vector_contract"]
    require(vector.get("message_profile") == "U64BE_LENGTH_PREFIXED_ASCII_DOMAIN_AND_EXACT_RAW_CANONICAL_FRAME", "message profile")
    for track in vector["tracks"]:
        track_id = track["track_id"]
        frame = frames.get(track_id)
        require(frame is not None, "frame track")
        domain = track["domain_ascii"].encode("ascii")
        message = len(domain).to_bytes(8, "big") + domain + len(frame).to_bytes(8, "big") + frame
        require(len(domain) == track["domain_bytes"], "domain length")
        require(len(frame) == track["canonical_frame_bytes"], "frame length")
        require(hashlib.sha256(frame).hexdigest() == track["canonical_frame_sha256"], "frame digest")
        require(len(message) == track["constructed_message_bytes"], "message length")
        require(hashlib.sha256(message).hexdigest() == track["constructed_message_sha256"], "message sha256")
        require(hashlib.sha512(message).hexdigest() == track["constructed_message_sha512"], "message sha512")
    return len(frames)


def clean_env() -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "TZ": "UTC",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
    }


def run_source(fixture: Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["/usr/bin/python3", "-S", "-P", str(SOURCE), str(fixture)],
        cwd=ROOT,
        env=clean_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=15,
    )


def validate_source_ast() -> None:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    allowed_imports = {"__future__", "hashlib", "json", "sys", "pathlib", "typing"}
    forbidden_calls = {"eval", "exec", "compile", "__import__", "generate_pkcs8", "sign", "urandom", "SystemRandom"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            require(all(alias.name.split(".")[0] in allowed_imports for alias in node.names), "source import")
        elif isinstance(node, ast.ImportFrom):
            require((node.module or "").split(".")[0] in allowed_imports, "source from import")
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            require(name not in forbidden_calls, f"forbidden source call {name}")


def mutate(record: dict[str, Any], edit: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    candidate = copy.deepcopy(record)
    edit(candidate)
    return candidate


def run_mutation_tests(record: dict[str, Any]) -> int:
    edits: list[Callable[[dict[str, Any]], None]] = [
        lambda r: r["semantic_amendment"]["trust_chain_semantics"].__setitem__("certificate_link_signature_count", 1),
        lambda r: r["semantic_amendment"]["trust_chain_semantics"].__setitem__("cryptographic_verification_count_on_positive_path", 2),
        lambda r: r["fixture_custodian_authority"].__setitem__("private_material_storage", "FILES_ALLOWED"),
        lambda r: r["fixture_custodian_authority"].__setitem__("consumption_failure_semantics", "FAILURE_ALLOWS_RETRY"),
        lambda r: r["output_contract"]["disallowed_committed_material"].remove("PRIVATE_KEY"),
        lambda r: r["output_contract"]["disallowed_committed_material"].remove("SEED"),
        lambda r: r["output_contract"]["generation_receipt_required_fields"].__setitem__(0, "replacement_field"),
        lambda r: r["separation_of_duties"].__setitem__("fixture_custodian_lane", r["separation_of_duties"]["implementer_lane"]),
        lambda r: next(item for item in r["state_machine"]["transitions"] if item["event"] == "PROCESS_FAILURE_OR_CONTRACT_DRIFT_AFTER_MAIN_ENTRY").__setitem__("to", "AUTHORIZED_ONE_SHOT_FIXTURE_CUSTODIAN_PENDING_PROCESS_START"),
        lambda r: r["semantic_amendment"]["trust_chain_semantics"].__setitem__("policy_chain_binding", "AUTHENTICATION_BUNDLE_SUPPLIED"),
        lambda r: r["synthetic_vector_contract"].__setitem__("message_profile", "UNFRAMED"),
        lambda r: r["synthetic_vector_contract"]["tracks"][0].__setitem__("active_leaf_key_version", "LATEST"),
        lambda r: r["boundary"].__setitem__("runtime_authority", True),
        lambda r: r["nonclaims"].__setitem__("track_subject_binding_implemented", True),
        lambda r: r["fixture_custodian_authority"].__setitem__("exact_keypair_generation_count", True),
        lambda r: r["predecessor"].__setitem__("authority_integration_commit", "0" * 40),
    ]
    with tempfile.TemporaryDirectory(prefix="ab-amendment-check-") as directory:
        root = Path(directory)
        for index, edit in enumerate(edits):
            candidate = mutate(record, edit)
            rejected = False
            try:
                validate_record(candidate)
            except CheckFailed:
                rejected = True
            require(rejected, f"independent mutation accepted {index}")
            path = root / f"mutation-{index}.json"
            path.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
            result = run_source(path)
            require(result.returncode != 0, f"source mutation accepted {index}")
        duplicate = b'{"schema":"x","schema":"y"}'
        duplicate_path = root / "duplicate.json"
        duplicate_path.write_bytes(duplicate)
        duplicate_rejected = False
        try:
            load_json_bytes(duplicate)
        except CheckFailed:
            duplicate_rejected = True
        require(duplicate_rejected, "checker duplicate key accepted")
        require(run_source(duplicate_path).returncode != 0, "source duplicate key accepted")
    return len(edits) + 1


def validate_manifest(record: dict[str, Any]) -> int:
    manifest = load_json_bytes(MANIFEST.read_bytes())
    require(isinstance(manifest, dict), "manifest object")
    require(set(manifest) == {
        "contract_sha256", "date", "dependency_artifact_raw_sha256", "next_unit",
        "packet_path_modes", "predecessor_authority_receipts", "raw_sha256",
        "schema", "schema_version", "source_baseline_commit", "status",
    }, "manifest keys")
    require(manifest.get("schema") == "agent_bridge.biocortex_ab_track_b.bootstrap_trust_fixture_custodian_one_shot_authority_amendment_pack.v1", "manifest schema")
    require(type(manifest.get("schema_version")) is int and manifest.get("schema_version") == 1, "manifest version")
    require(manifest.get("date") == "2026-07-17", "manifest date")
    require(manifest.get("contract_sha256") == "c473be2365a38addebf6565932eeb811636401d8bef8129b791af662733d77fe", "manifest contract")
    require(manifest.get("next_unit") == "BOOTSTRAP_TRUST_PUBLIC_ONLY_VECTOR_SUPPLY_AND_GENERATION_PROVENANCE_RECEIPT_FREEZE", "manifest next unit")
    require(manifest.get("status") == "FROZEN_OWNER_AUTHORIZED_AMENDMENT_PENDING_INTEGRATED_FULL_GATE", "manifest status")
    require(manifest.get("source_baseline_commit") == "a18f0af7b4cbaa971143c71080a2b49786a7f7a3", "manifest baseline")
    expected_paths = {
        "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-bootstrap-trust-fixture-custodian-one-shot-authority-amendment-v1-pack.md": "100644",
        "scripts/check-biocortex-ab-track-b-bootstrap-trust-fixture-custodian-one-shot-authority-amendment-v1-pack.sh": "100755",
        "scripts/eval/biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1.py": "100644",
        "scripts/eval/check_biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1_pack.py": "100644",
        "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1_owner_decision_v0.json": "100644",
        "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1_pack.expected.v0.tsv": "100644",
        "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1_pack_v0.json": "100644",
    }
    require(manifest.get("packet_path_modes") == expected_paths, "manifest path modes")
    expected_dependencies = {
        "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-v1.schema.json": "e8cb4964f86de39b16d553537467006454c720dc8bfa8d36e370189627328f55",
        "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.md": "841df2168eaaabfb4c17dcc15e5adfd5ed9c833eb6e40bc2bd9998833549a78b",
        "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.md": "a93fd00b9dc43f8b9d3717fd07bf3a2eef734724834d75d122d2e8bbbe6e3149",
        "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh": "16fdb98784a567222e98a15cf9afc7947a70055957b1e8fc1735a9d03719daa5",
        "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.sh": "464b975d61403759221fd3aa41da4c38de12f4ec946b161100d23edadbc2b174",
        "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py": "f1168fad03ac6366e8d6501cbd4da3a2969d25cc6ef9f5bf85c0624de9ae545c",
        "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1.py": "bfa3badbe2b467fbed610d5acb42ef21f1aec2ceb2d5ccf2c218fecfe438eed1",
        "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.py": "7c5f1dcd53db8bdf9360e8e00a6495daa40b97d21fbf4efa1f9f3392bfbd6136",
        "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.py": "76e0960cb9afa0e4e655ec122b600fe489a31acd5a7edf659d2fff4727ef0dcf",
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.expected.v0.tsv": "79502975f438ed644306a392131d102e2efadae37560b3489c91547a0125e43f",
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json": "05f2fad20896cd108f0695253c617cd0c050e80ae947ec4c90f7d7684e3e344b",
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_v0.json": "e521a7aab3a3fa00dacade4da1bf88834680a878d4de425f77918734655e255e",
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.expected.v0.tsv": "775ecfa5169509a5fe0e5a900d8644f47b6b4cf64a1778c7d4ed52214115c847",
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_synthetic_v0.json": "324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9",
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_v0.json": "9c7ba09368ebd610452ca2799226c1f57dcb63fedabb0319f4b39bc071277d04",
    }
    require(manifest.get("dependency_artifact_raw_sha256") == expected_dependencies, "manifest dependencies")
    require(manifest.get("predecessor_authority_receipts") == {
        "fast_line_count": 126,
        "fast_stdout_sha256": "2ec3b62897c4237b3d2f418a794b64511154ef436bb887b25c7a8418880c6e7c",
        "full_line_count": 127,
        "full_stdout_sha256": "ad5614db7653c4387f57c8e3d5bb52e40d2b21edeeecda7fc2c9bb5f2265dbb9",
    }, "manifest predecessor receipts")
    actual_raw = {
        str(SOURCE.relative_to(ROOT)): sha256_path(SOURCE),
        str(FIXTURE.relative_to(ROOT)): sha256_path(FIXTURE),
        str(EXPECTED.relative_to(ROOT)): sha256_path(EXPECTED),
    }
    require(manifest.get("raw_sha256") == actual_raw, "manifest raw hashes")
    authority_subset = {path: digest for path, digest in expected_dependencies.items() if "bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1" in path or "bootstrap-trust-authentication-isolated-lab-implementation-authority-and-resource-binding-decision-v1" in path}
    require(len(authority_subset) == 7, "authority subset")
    require(record["predecessor"]["authority_artifact_raw_sha256"] == authority_subset, "fixture authority cross-binding")
    return len(expected_dependencies)


def main() -> int:
    try:
        fixture_raw = FIXTURE.read_bytes()
        require(hashlib.sha256(fixture_raw).hexdigest() == EXPECTED_RECORD_RAW_SHA256, "record raw oracle")
        record = load_json_bytes(fixture_raw)
        validate_record(record)
        messages = reconstruct_frozen_messages(record)
        validate_source_ast()
        result = run_source(FIXTURE)
        require(result.returncode == 0 and result.stderr == b"", "source release run")
        mutations = run_mutation_tests(record)
        dependencies = validate_manifest(record)
        expected = EXPECTED.read_bytes()
        output = result.stdout + (
            f"independent_checker\ttrue\n"
            f"independent_mutation_rejection_count\t{mutations}\n"
            f"frozen_message_reconstruction_count\t{messages}\n"
            f"source_ast_generation_surface_absent\ttrue\n"
            f"manifest_integrity_verified\ttrue\n"
            f"dependency_artifact_count\t{dependencies}\n"
            f"packet_path_count\t7\n"
            f"checker_status\tPASS\n"
        ).encode("ascii")
        require(output == expected, "expected TSV drift")
        sys.stdout.buffer.write(output)
        return 0
    except (OSError, json.JSONDecodeError, CheckFailed, subprocess.SubprocessError) as exc:
        print(f"amendment pack check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
