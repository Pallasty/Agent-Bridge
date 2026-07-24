#!/usr/bin/env python3
"""D29 verifies a D27 approval/resource bundle; it never invokes D5."""
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REQUIRED = ("approval.json", "approval.ed25519.sig", "approval-public-key.pem", "resource-receipt.json", "resource-receipt.ed25519.sig", "resource-public-key.pem")
MIN_SCRATCH_BYTES, MIN_INODES = 2_750_812_950, 13_622

class BundleError(ValueError): pass

def _pairs(xs: list[tuple[str, Any]]) -> dict[str, Any]:
    out = {}
    for k, v in xs:
        if k in out: raise BundleError("duplicate JSON key")
        out[k] = v
    return out

def _json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if not raw or len(raw) > 65536: raise BundleError("JSON size drift")
    try: value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_float=lambda _: (_ for _ in ()).throw(BundleError("float forbidden")))
    except (UnicodeError, json.JSONDecodeError) as exc: raise BundleError("invalid JSON") from exc
    if not isinstance(value, dict): raise BundleError("JSON object required")
    return value

def _verify(key: Path, message: Path, signature: Path) -> None:
    probe = subprocess.run(["openssl", "pkey", "-pubin", "-in", str(key), "-text", "-noout"], capture_output=True, text=True)
    if probe.returncode or "ED25519" not in probe.stdout.upper(): raise BundleError("public key is not Ed25519")
    verified = subprocess.run(["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(key), "-rawin", "-in", str(message), "-sigfile", str(signature)], capture_output=True)
    if verified.returncode: raise BundleError("Ed25519 signature verification failed")

def verify(bundle: Path) -> dict[str, Any]:
    bundle = Path(bundle)
    if not bundle.is_dir() or bundle.is_symlink(): raise BundleError("bundle directory unsafe")
    if {p.name for p in bundle.iterdir()} != set(REQUIRED): raise BundleError("bundle file set drift")
    for name in REQUIRED:
        p = bundle / name
        if not p.is_file() or p.is_symlink() or p.stat().st_size > 65536: raise BundleError("bundle member unsafe")
    _verify(bundle/"approval-public-key.pem", bundle/"approval.json", bundle/"approval.ed25519.sig")
    _verify(bundle/"resource-public-key.pem", bundle/"resource-receipt.json", bundle/"resource-receipt.ed25519.sig")
    import fh_l8_micro_action_authorization_d27 as d27
    approval, receipt, request = _json(bundle/"approval.json"), _json(bundle/"resource-receipt.json"), d27.request()
    d27.validate_approval(request, approval)
    need = {"schema_version","request_id","resource_authority","receipt_id","not_before_unix_ns","not_after_unix_ns","exclusive_execution_slot","isolation_id","scratch_free_bytes","scratch_free_inodes","memory_max_bytes","swap_max_bytes","wall_seconds"}
    if set(receipt) != need or receipt.get("schema_version") != 1 or receipt.get("request_id") != request["request_id"]: raise BundleError("receipt schema or request drift")
    ints = ("not_before_unix_ns","not_after_unix_ns","scratch_free_bytes","scratch_free_inodes","memory_max_bytes","swap_max_bytes","wall_seconds")
    if any(type(receipt[x]) is not int for x in ints) or receipt["not_after_unix_ns"] <= receipt["not_before_unix_ns"]: raise BundleError("receipt integer/time drift")
    if not all(isinstance(receipt[x], str) and receipt[x] for x in ("resource_authority","receipt_id","exclusive_execution_slot","isolation_id")): raise BundleError("receipt identity drift")
    if receipt["resource_authority"] == request["requesting_authority"] or receipt["scratch_free_bytes"] < MIN_SCRATCH_BYTES or receipt["scratch_free_inodes"] < MIN_INODES: raise BundleError("receipt independence or capacity drift")
    if {k: receipt[k] for k in ("memory_max_bytes","swap_max_bytes","wall_seconds")} != request["resource_ceiling"]: raise BundleError("receipt resource scope drift")
    return {"status":"VERIFIED_D29_SIGNED_MICRO_ACTION_BUNDLE_ADMISSIBLE_NOT_EXECUTED","approval_sha256":hashlib.sha256((bundle/"approval.json").read_bytes()).hexdigest(),"receipt_sha256":hashlib.sha256((bundle/"resource-receipt.json").read_bytes()).hexdigest(),"synthetic_kernel_fixture_authorized":True,"real_packed_q3_reads":0,"scientific_action_calls":0,"full_53_scientific_execution_authorized":False,"next_gate":"ISOLATED_SINGLE_MICRO_ACTION_AND_MEASURED_RECEIPT"}
