#!/usr/bin/env python3
"""Build S608 static authority, CPU INT4, nonce, and receipt contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_MODEL_FILES = (
    "code_predictor.onnx", "codec_embed.onnx", "residual_embed.onnx",
    "talker_cache.onnx", "text_embed.onnx", "tok_decoder.onnx", "tok_encoder.onnx",
)
OUTPUT_ROOT = Path("/Data/Models/agent-bridge/evidence/story-render")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required:{path}")
    return value


def _validate_s607(value: dict[str, Any]) -> None:
    bound = {key: value[key] for key in (
        "source", "evidence", "call_order", "boundaries", "blockers",
        "implementation_present", "deployment_authorized", "execution_authorized", "runtime_effects")}
    if (value.get("schema") != "agent_bridge.story_bounded_render_executor_source_review.v1"
            or value.get("decision") != "source_implementation_accepted_runtime_blocked"
            or value.get("next_gate") != "story_executor_authority_model_nonce_contract"
            or value.get("execution_authorized") is not False
            or any(value.get("runtime_effects", {}).values())
            or _digest(bound) != value.get("review_sha256")):
        raise ValueError("S607 source review invalid")


def build_contract(*, source_review_path: Path, snapshot_audit_path: Path,
                   snapshot_path: Path, executor_path: Path,
                   receipt_schema_path: Path, nonce_store_path: Path) -> dict[str, Any]:
    s607 = _read(source_review_path)
    _validate_s607(s607)
    audit = _read(snapshot_audit_path)
    if audit.get("snapshot") != str(snapshot_path):
        raise ValueError("CPU INT4 audit snapshot mismatch")
    audited = {row["path"]: row for row in audit.get("integrity", {}).get("file_hashes", [])}
    wanted = [f"cpu_int4/{name}" for name in EXPECTED_MODEL_FILES]
    if any(path not in audited or len(audited[path].get("sha256", "")) != 64 for path in wanted):
        raise ValueError("CPU INT4 audit incomplete")

    cpu_dir = snapshot_path / "cpu_int4"
    manifest_path = cpu_dir / "manifest.json"
    inference_path = snapshot_path / "inference.py"
    manifest = _read(manifest_path)
    manifest_files = sorted(row.get("filename") for row in manifest.get("sub_models", {}).values())
    if (manifest_files != sorted(EXPECTED_MODEL_FILES)
            or manifest.get("precision") != "int4"
            or manifest.get("execution_provider") != "CPUExecutionProvider"):
        raise ValueError("CPU INT4 manifest invalid")
    if (_sha256_file(manifest_path) != audited.get("cpu_int4/manifest.json", {}).get("sha256")
            or not inference_path.is_file() or not executor_path.is_file()):
        raise ValueError("small model control file mismatch")
    rows = []
    for relative in wanted:
        path = snapshot_path / relative
        row = audited[relative]
        if not path.is_file() or path.stat().st_size != row["size"]:
            raise ValueError("CPU INT4 model size mismatch")
        rows.append({"path": relative, "size": row["size"], "sha256": row["sha256"]})

    nonce = nonce_store_path
    try:
        nonce.resolve().relative_to(OUTPUT_ROOT.resolve())
        under_output = True
    except ValueError:
        under_output = False
    if not nonce.is_absolute() or under_output or nonce.suffix != ".sqlite3":
        raise ValueError("nonce store path unsafe")
    receipt_schema = _read(receipt_schema_path)
    if receipt_schema.get("$id") != "agent_bridge.story_bounded_render_receipt.v1":
        raise ValueError("receipt schema invalid")

    authority = {
        "algorithm": "hmac-sha256", "domain_separator": "agent-bridge.story-render-authorization.v1",
        "canonicalization": "utf8-jcs-rfc8785", "maximum_ttl_seconds": 600,
        "signed_fields": ["authorization_id", "contract_sha256", "preflight_sha256", "output_directory",
                          "action", "issued_at", "expires_at", "single_use_nonce", "issuer", "subject", "key_id"],
        "proof_field": "mac_sha256", "secret_material_in_envelope": False,
        "constant_time_comparison_required": True, "key_custody": "external_secure_runtime_configuration",
        "key_installed_now": False,
    }
    model = {
        "snapshot": str(snapshot_path), "variant": "cpu_int4", "execution_provider": "CPUExecutionProvider",
        "manifest_path": str(manifest_path), "manifest_sha256": _sha256_file(manifest_path),
        "inference_path": str(inference_path), "inference_sha256": _sha256_file(inference_path),
        "snapshot_audit_path": str(snapshot_audit_path.resolve()),
        "snapshot_audit_file_sha256": _sha256_file(snapshot_audit_path), "files": rows,
        "large_files_rehashed_now": False, "large_files_size_checked_now": True,
        "runtime_verifier_must_stream_sha256_before_nonce_consumption": True,
    }
    nonce_contract = {
        "path": str(nonce), "backend": "sqlite3", "parent_mode": "0700", "database_mode": "0600",
        "reject_symlinks": True, "single_writer_transaction": "BEGIN IMMEDIATE",
        "unique_key": "single_use_nonce", "caller_configurable": False,
        "outside_render_output_root": True, "installed_now": False,
    }
    receipt = {"path": str(receipt_schema_path.resolve()), "$schema": receipt_schema["$schema"],
               "schema_id": receipt_schema["$id"], "sha256": _sha256_file(receipt_schema_path),
               "playback_authorized": False, "memory_authorized": False}
    runtime = {"created_key": False, "created_nonce_store": False, "imported_executor": False,
               "called_executor": False, "loaded_model": False, "executed_onnx": False,
               "rendered_audio": False, "played_audio": False, "recorded_audio": False, "wrote_memory": False}
    blockers = ["authority_and_model_verifiers_not_implemented", "secure_key_and_nonce_paths_not_installed",
                "executor_not_wired_to_fixed_contracts"]
    bound = {"evidence": {"s607_review_file_sha256": _sha256_file(source_review_path),
                           "s607_review_sha256": s607["review_sha256"],
                           "executor_sha256": _sha256_file(executor_path)},
             "authority_proof": authority, "model_bundle": model, "nonce_store": nonce_contract,
             "receipt_schema": receipt, "blockers": blockers, "execution_authorized": False,
             "runtime_effects": runtime}
    return {"schema": "agent_bridge.story_executor_authority_model_nonce_contract.v1",
            "status": "story_executor_authority_model_nonce_contract_reviewable",
            "decision": "static_contract_complete_runtime_configuration_uninstalled", **bound,
            "contract_sha256": _digest(bound),
            "claims": {"authority_proof_format_defined": True, "cpu_int4_bundle_bound": True,
                       "nonce_custody_defined": True, "render_receipt_schema_defined": True,
                       "verifiers_implemented": False, "real_model_executed": False},
            "next_gate": "story_executor_authority_model_nonce_verifier_implementation_review"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-review", type=Path, required=True)
    parser.add_argument("--snapshot-audit", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--executor", type=Path, required=True)
    parser.add_argument("--receipt-schema", type=Path, required=True)
    parser.add_argument("--nonce-store", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    value = build_contract(source_review_path=args.source_review, snapshot_audit_path=args.snapshot_audit,
        snapshot_path=args.snapshot, executor_path=args.executor, receipt_schema_path=args.receipt_schema,
        nonce_store_path=args.nonce_store)
    print(json.dumps(value, ensure_ascii=False, indent=2 if args.pretty else None,
                     separators=None if args.pretty else (",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
