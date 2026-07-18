#!/usr/bin/env python3
"""Independent checker for the bootstrap-trust public vector supply pack."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


sys.dont_write_bytecode = True


CHECKER_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b.bootstrap_trust_public_only_vector_"
    "supply_and_generation_provenance_receipt_freeze_pack_checker.v1"
)
BASELINE_COMMIT = "b4126a4192137e741e32ebb86170884b81185cbf"
SOURCE_RAW_SHA256 = "2a963bfab7e938deb3fce9c40765694e62d49c324322dec33b31d7ca459f661d"
VECTOR_RAW_SHA256 = "a87e0883a42ca69fe3a0348b4ffe44c153882f8dcc93eb67db1ea048d53851d7"
RECEIPT_RAW_SHA256 = "bdd85c98b7adfddf5eff5202984862c29b95f17b152a621198ac405d81ba1ee0"
EXPECTED_RAW_SHA256 = "c684184bad18fa1265a6aa5e7d5ac0c7111aa49962e66a47b4b24f6bc898e79a"
FRAME_FIXTURE_RAW_SHA256 = "324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9"
SOURCE_STDOUT_SHA256 = "c684184bad18fa1265a6aa5e7d5ac0c7111aa49962e66a47b4b24f6bc898e79a"
SOURCE_STDOUT_LINE_COUNT = 41

SOURCE_PATH = "scripts/eval/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1.py"
CHECKER_PATH = "scripts/eval/check_biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack.py"
VECTOR_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack_public_vector_bundle_v0.json"
RECEIPT_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack_generation_provenance_receipt_v0.json"
EXPECTED_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack.expected.v0.tsv"
MANIFEST_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack_v0.json"
REPORT_PATH = "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-bootstrap-trust-public-only-vector-supply-and-generation-provenance-receipt-freeze-v1-pack.md"
GATE_PATH = "scripts/check-biocortex-ab-track-b-bootstrap-trust-public-only-vector-supply-and-generation-provenance-receipt-freeze-v1-pack.sh"

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_IMPORT_ROOTS = {
    "asyncio",
    "http",
    "random",
    "requests",
    "secrets",
    "socket",
    "ssl",
    "subprocess",
    "urllib",
}
FORBIDDEN_CALL_NAMES = {
    "ed25519_public_key",
    "ed25519_sign",
    "generate_pkcs8",
    "keygen",
    "sign",
    "SystemRandom",
    "urlopen",
}


class CheckError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise CheckError(code)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CheckError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def load_canonical(raw: bytes, code: str) -> dict[str, Any]:
    require(raw.endswith(b"\n") and not raw.endswith(b"\n\n"), f"{code}_LF")
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckError(f"{code}_JSON") from exc
    require(type(value) is dict, f"{code}_OBJECT")
    encoded = canonical(value)
    require(encoded == raw, f"{code}_CANONICAL")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def load_source(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("bootstrap_supply_source", path)
    require(spec is not None and spec.loader is not None, "SOURCE_IMPORT_SPEC")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_source_surface(source_raw: bytes) -> tuple[int, int]:
    try:
        tree = ast.parse(source_raw.decode("utf-8", "strict"))
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise CheckError("SOURCE_AST") from exc
    imports: set[str] = set()
    calls: set[str] = set()
    review_functions = 0
    verify_functions = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            review_functions += node.name == "review_supply"
            verify_functions += node.name == "_verify"
    require(not (imports & FORBIDDEN_IMPORT_ROOTS), "SOURCE_FORBIDDEN_IMPORT")
    require(not (calls & FORBIDDEN_CALL_NAMES), "SOURCE_FORBIDDEN_CRYPTO_OR_NETWORK_CALL")
    require(review_functions == 1 and verify_functions == 1, "SOURCE_ENTRYPOINTS")
    require(b"PRIVATE KEY" not in source_raw and b"BEGIN PRIVATE" not in source_raw, "SOURCE_PRIVATE_MATERIAL_MARKER")
    return len(imports), len(calls)


def expect_reject(action: Callable[[], Any], label: str) -> None:
    try:
        action()
    except Exception:
        return
    raise CheckError(f"MUTATION_ACCEPTED_{label}")


def run_mutations(module: Any, vector_raw: bytes, receipt_raw: bytes, frame_raw: bytes) -> int:
    vector = load_canonical(vector_raw, "VECTOR")
    receipt = load_canonical(receipt_raw, "RECEIPT")
    mutations = 0

    def reject_candidate(candidate_vector: dict[str, Any], candidate_receipt: dict[str, Any] | None = None, label: str = "VECTOR") -> None:
        nonlocal mutations
        vraw = canonical(candidate_vector)
        r = copy.deepcopy(receipt if candidate_receipt is None else candidate_receipt)
        r["vector_bundle_sha256"] = sha256(vraw)
        expect_reject(lambda: module.review_supply(vraw, canonical(r), frame_raw, enforce_frozen_raw_hashes=False), label)
        mutations += 1

    def mutate_vector(label: str, change: Callable[[dict[str, Any]], None]) -> None:
        candidate = copy.deepcopy(vector)
        change(candidate)
        reject_candidate(candidate, label=label)

    mutate_vector("EXTRA_FIELD", lambda v: v.__setitem__("seed", "00"))
    mutate_vector("TRACK_ORDER", lambda v: v["tracks"].reverse())
    mutate_vector("CHAIN_ORDER", lambda v: v["tracks"][0]["chain"].reverse())
    mutate_vector("ROOT_ROLE", lambda v: v["tracks"][0]["chain"][0].__setitem__("role", "WRONG"))
    mutate_vector("LEAF_VERSION", lambda v: v["tracks"][0]["chain"][2].__setitem__("key_version", "LATEST"))
    mutate_vector("REVOKED_VERSION", lambda v: v["tracks"][0]["revoked_leaf"].__setitem__("key_version", "KAT_MANAGED_LEAF_KEY_VERSION_2"))
    mutate_vector("POLICY_REVISION", lambda v: v["tracks"][0].__setitem__("policy_revision", "WRONG"))
    mutate_vector("REVOCATION_REVISION", lambda v: v["tracks"][1].__setitem__("revocation_snapshot_revision", "WRONG"))
    mutate_vector("SIGNATURE_DOMAIN", lambda v: v["tracks"][0].__setitem__("signature_domain", v["tracks"][1]["signature_domain"]))
    mutate_vector("MESSAGE_SHA256", lambda v: v["tracks"][0].__setitem__("message_sha256", "0" * 64))
    mutate_vector("FRAME_SHA256", lambda v: v["tracks"][1].__setitem__("canonical_frame_sha256", "0" * 64))
    mutate_vector("DUPLICATE_PUBLIC_KEY", lambda v: v["tracks"][0]["chain"][1].__setitem__("public_key_hex", v["tracks"][0]["chain"][0]["public_key_hex"]))
    mutate_vector("IDENTITY_PUBLIC_KEY", lambda v: v["tracks"][0]["chain"][0].__setitem__("public_key_hex", "01" + "00" * 31))
    mutate_vector("UPPERCASE_PUBLIC_KEY", lambda v: v["tracks"][0]["chain"][0].__setitem__("public_key_hex", v["tracks"][0]["chain"][0]["public_key_hex"].upper()))
    mutate_vector("SIGNATURE_BIT", lambda v: v["tracks"][0].__setitem__("signature_hex", ("0" if v["tracks"][0]["signature_hex"][0] != "0" else "1") + v["tracks"][0]["signature_hex"][1:]))
    mutate_vector("CROSS_TRACK_SIGNATURE", lambda v: v["tracks"][0].__setitem__("signature_hex", v["tracks"][1]["signature_hex"]))
    mutate_vector("IDENTITY_R", lambda v: v["tracks"][0].__setitem__("signature_hex", "01" + "00" * 31 + v["tracks"][0]["signature_hex"][64:]))
    mutate_vector("SCALAR_S_GE_L", lambda v: v["tracks"][0].__setitem__("signature_hex", v["tracks"][0]["signature_hex"][:64] + int(module._L).to_bytes(32, "little").hex()))

    pretty = (json.dumps(vector, sort_keys=True, indent=2) + "\n").encode()
    expect_reject(lambda: module.review_supply(pretty, receipt_raw, frame_raw, enforce_frozen_raw_hashes=False), "VECTOR_NONCANONICAL")
    mutations += 1
    duplicate_vector = vector_raw[:-2] + b',"schema":"duplicate"}\n'
    expect_reject(lambda: module.review_supply(duplicate_vector, receipt_raw, frame_raw, enforce_frozen_raw_hashes=False), "VECTOR_DUPLICATE_KEY")
    mutations += 1

    receipt_mutations: list[tuple[str, str, Any]] = [
        ("RECEIPT_CONSUMED", "authority_single_use_consumed", False),
        ("RECEIPT_GATE", "authority_gate_sha256", "0" * 64),
        ("RECEIPT_SOURCE", "ephemeral_generator_source_sha256", "0" * 64),
        ("RECEIPT_KEYPAIR_COUNT", "keypair_generation_count", 5),
        ("RECEIPT_SIGNATURE_COUNT", "signature_generation_count", 1),
        ("RECEIPT_RETRY", "retry_count", 1),
        ("RECEIPT_NETWORK", "network_attempt_count", 1),
        ("RECEIPT_PRIVATE_WRITE", "private_material_file_write_count", 1),
        ("RECEIPT_CLEANUP", "generator_namespace_cleanup_complete", False),
        ("RECEIPT_SECURE_ERASURE", "secure_erasure_claimed", True),
    ]
    for label, key, value in receipt_mutations:
        candidate = copy.deepcopy(receipt)
        candidate[key] = value
        expect_reject(lambda c=candidate: module.review_supply(vector_raw, canonical(c), frame_raw, enforce_frozen_raw_hashes=False), label)
        mutations += 1
    extra_receipt = copy.deepcopy(receipt)
    extra_receipt["endpoint"] = "forbidden"
    expect_reject(lambda: module.review_supply(vector_raw, canonical(extra_receipt), frame_raw, enforce_frozen_raw_hashes=False), "RECEIPT_EXTRA")
    mutations += 1
    duplicate_receipt = receipt_raw[:-2] + b',"retry_count":0}\n'
    expect_reject(lambda: module.review_supply(vector_raw, duplicate_receipt, frame_raw, enforce_frozen_raw_hashes=False), "RECEIPT_DUPLICATE")
    mutations += 1
    broken_frame = frame_raw[:-2] + (b"0" if frame_raw[-2:-1] != b"0" else b"1") + frame_raw[-1:]
    expect_reject(lambda: module.review_supply(vector_raw, receipt_raw, broken_frame, enforce_frozen_raw_hashes=False), "FRAME_RAW_HASH")
    mutations += 1
    require(mutations == 33, "MUTATION_COUNT")
    return mutations


def validate_manifest(manifest_raw: bytes, root: Path) -> None:
    manifest = load_canonical(manifest_raw, "MANIFEST")
    require(set(manifest) == {
        "date",
        "dependency_artifact_raw_sha256",
        "expected",
        "generation",
        "next_unit",
        "nonclaims",
        "packet_path_modes",
        "raw_sha256",
        "date",
        "schema",
        "schema_version",
        "source_baseline_commit",
        "state",
        "status",
    }, "MANIFEST_FIELDS")
    require(manifest["schema"] == "agent_bridge.biocortex_ab_track_b.bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_pack_manifest.v1", "MANIFEST_SCHEMA")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1, "MANIFEST_VERSION")
    require(manifest["source_baseline_commit"] == BASELINE_COMMIT and manifest["date"] == "2026-07-17", "MANIFEST_BASELINE")
    expected_paths = {SOURCE_PATH, CHECKER_PATH, VECTOR_PATH, RECEIPT_PATH, EXPECTED_PATH, MANIFEST_PATH, REPORT_PATH, GATE_PATH}
    raw_paths = {SOURCE_PATH, VECTOR_PATH, RECEIPT_PATH, EXPECTED_PATH}
    require(set(manifest["raw_sha256"]) == raw_paths, "MANIFEST_RAW_PATHS")
    for path in raw_paths:
        require(manifest["raw_sha256"][path] == sha256((root / path).read_bytes()), f"MANIFEST_HASH_{path}")
    require(set(manifest["packet_path_modes"]) == expected_paths, "MANIFEST_MODE_PATHS")
    require(manifest["packet_path_modes"] == {path: ("100755" if path == GATE_PATH else "100644") for path in expected_paths}, "MANIFEST_MODES")
    for path in expected_paths:
        candidate = root / path
        require(candidate.is_file() and not candidate.is_symlink(), f"MANIFEST_PACKET_FILE_{path}")
    dependencies = manifest["dependency_artifact_raw_sha256"]
    require(type(dependencies) is dict and len(dependencies) == 15, "MANIFEST_DEPENDENCY_COUNT")
    for path, digest in dependencies.items():
        require(type(path) is str and type(digest) is str and SHA_RE.fullmatch(digest) is not None, "MANIFEST_DEPENDENCY_ENTRY")
        require((root / path).is_file() and sha256((root / path).read_bytes()) == digest, f"MANIFEST_DEPENDENCY_HASH_{path}")
    require(manifest["expected"] == {
        "checker_stdout_line_count": 20,
        "directed_mutation_count": 33,
        "public_key_count": 6,
        "source_stdout_line_count": 41,
        "source_stdout_sha256": SOURCE_STDOUT_SHA256,
        "strict_signature_verification_count": 2,
        "track_count": 2,
    }, "MANIFEST_EXPECTED")
    require(manifest["generation"] == {
        "authority_full_receipt_sha256": "a40e9a208209de3a24904dc0957515e11f247ee7e07c070ff2306f32e553d77f",
        "authority_gate_sha256": "21c5aa21cebf7e37767a2ec0bcd38bd8b28839bd9b825c86e81920a2ce20aef0",
        "authority_integration_commit": BASELINE_COMMIT,
        "generator_source_sha256": "62a8e32eef9e9a5560cd6dacfce5a181761196cef18a77508eb8552c1e20f083",
        "keypair_generation_count": 6,
        "process_entry_count": 1,
        "retry_count": 0,
        "signature_generation_count": 2,
        "vector_bundle_sha256": VECTOR_RAW_SHA256,
        "generation_receipt_sha256": RECEIPT_RAW_SHA256,
    }, "MANIFEST_GENERATION")
    require(manifest["status"] == "FROZEN_PUBLIC_ONLY_VECTOR_SUPPLY_PENDING_INTEGRATED_FULL_GATE", "MANIFEST_STATUS")
    require(manifest["next_unit"] == "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_TRUST_CHAIN_EXACT_KEY_VERSION_DECLARED_ROLE_AND_REVOCATION_VERIFIER_ISOLATED_LAB_IMPLEMENTATION", "MANIFEST_NEXT_UNIT")
    require(manifest["state"] == {
        "fixture_generation_authority_single_use_consumed": True,
        "fixture_generation_authority_state": "CONSUMED_SCOPE_COMPLETE_PUBLIC_OUTPUT_AVAILABLE",
        "underlying_implementation_authority_effective": True,
        "underlying_implementation_authority_single_use_consumed": False,
    }, "MANIFEST_STATE")
    require(manifest["nonclaims"] == {
        "application_claim_authorized": False,
        "certificate_path_validation_defined": False,
        "cryptographic_chain_link_signatures_defined": False,
        "global_single_use_proved": False,
        "memory_zeroization_proved": False,
        "private_material_secure_erasure_proved": False,
        "production_authentication_proved": False,
        "production_security_approval": False,
        "provider_cryptographic_compatibility_proved": False,
        "real_evidence_authenticated": False,
        "revocation_currentness_proved": False,
        "role_scope_authorization_implemented": False,
        "scientific_claim_authorized": False,
        "swap_exclusion_proved": False,
        "track_subject_binding_implemented": False,
    }, "MANIFEST_NONCLAIMS")


def check(source: Path, vector: Path, receipt: Path, expected: Path, frame: Path, manifest: Path | None) -> dict[str, str]:
    source_raw = source.read_bytes()
    vector_raw = vector.read_bytes()
    receipt_raw = receipt.read_bytes()
    expected_raw = expected.read_bytes()
    frame_raw = frame.read_bytes()
    require(sha256(source_raw) == SOURCE_RAW_SHA256, "SOURCE_RAW_SHA256")
    require(sha256(vector_raw) == VECTOR_RAW_SHA256, "VECTOR_RAW_SHA256")
    require(sha256(receipt_raw) == RECEIPT_RAW_SHA256, "RECEIPT_RAW_SHA256")
    require(sha256(expected_raw) == EXPECTED_RAW_SHA256, "EXPECTED_RAW_SHA256")
    require(sha256(frame_raw) == FRAME_FIXTURE_RAW_SHA256, "FRAME_RAW_SHA256")
    import_count, call_count = check_source_surface(source_raw)
    module = load_source(source)
    result = module.review_supply(vector_raw, receipt_raw, frame_raw)
    rendered = module._render(result).encode("utf-8")
    require(rendered == expected_raw, "SOURCE_EXPECTED_BYTES")
    require(sha256(rendered) == SOURCE_STDOUT_SHA256 and rendered.count(b"\n") == SOURCE_STDOUT_LINE_COUNT, "SOURCE_STDOUT_ORACLE")
    process = subprocess.run(
        [sys.executable, "-S", "-P", str(source), str(vector), str(receipt), str(frame)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0"},
    )
    require(process.returncode == 0 and process.stderr == b"" and process.stdout == expected_raw, "SOURCE_SUBPROCESS")
    mutation_count = run_mutations(module, vector_raw, receipt_raw, frame_raw)

    manifest_validated = False
    if manifest is not None:
        manifest_raw = manifest.read_bytes()
        root = source.resolve().parents[2]
        validate_manifest(manifest_raw, root)
        manifest_validated = True

    return {
        "schema": CHECKER_SCHEMA,
        "status": "PUBLIC_ONLY_VECTOR_SUPPLY_PACK_CHECK_PASS",
        "baseline_commit": BASELINE_COMMIT,
        "source_raw_sha256": sha256(source_raw),
        "vector_raw_sha256": sha256(vector_raw),
        "generation_receipt_raw_sha256": sha256(receipt_raw),
        "expected_raw_sha256": sha256(expected_raw),
        "frame_fixture_raw_sha256": sha256(frame_raw),
        "source_stdout_sha256": sha256(rendered),
        "source_stdout_line_count": str(rendered.count(b"\n")),
        "directed_mutation_count": str(mutation_count),
        "track_count": "2",
        "public_key_count": "6",
        "distinct_public_key_count": "6",
        "strict_signature_verification_count": "2",
        "source_forbidden_import_count": "0",
        "source_forbidden_crypto_or_network_call_count": "0",
        "source_ast_import_count": str(import_count),
        "source_ast_call_name_count": str(call_count),
        "manifest_validated": "true" if manifest_validated else "false",
    }


def render(result: dict[str, str]) -> str:
    return "".join(f"{key}\t{value}\n" for key, value in result.items())


def main(argv: list[str]) -> int:
    if len(argv) not in (6, 7):
        print("usage: checker SOURCE VECTOR RECEIPT EXPECTED FRAME [MANIFEST]", file=sys.stderr)
        return 2
    try:
        result = check(
            Path(argv[1]),
            Path(argv[2]),
            Path(argv[3]),
            Path(argv[4]),
            Path(argv[5]),
            Path(argv[6]) if len(argv) == 7 else None,
        )
    except (OSError, CheckError) as exc:
        print(f"FAIL\t{exc}", file=sys.stderr)
        return 1
    sys.stdout.write(render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
