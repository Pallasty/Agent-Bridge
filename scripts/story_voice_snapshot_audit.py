#!/usr/bin/env python3
"""Fail-closed static audit for a downloaded voice-model snapshot.

This module never imports candidate Python, loads ONNX, installs dependencies,
or invokes an inference provider.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any


EXPECTED_VARIANTS = {
    "cpu_fp16",
    "cpu_fp32",
    "cpu_int4",
    "cuda_fp16",
    "cuda_fp32",
    "cuda_int4",
}
LICENSE_NAMES = ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "NOTICE")
NETWORK_IMPORTS = {
    "aiohttp",
    "ftplib",
    "httpx",
    "requests",
    "socket",
    "urllib3",
}
PROCESS_MODULES = {"multiprocessing", "subprocess"}
DYNAMIC_CALLS = {"__import__", "compile", "eval", "exec"}


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute) and isinstance(
        node.func.value, ast.Name
    ):
        return f"{node.func.value.id}.{node.func.attr}"
    return None


def audit_python_source(path: Path, root: Path) -> dict[str, Any]:
    findings = set()
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError) as error:
        return {
            "path": _relative(path, root),
            "parsed": False,
            "executed": False,
            "findings": [f"parse_failed:{type(error).__name__}"],
        }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name.split(".", 1)[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [(node.module or "").split(".", 1)[0]]
        else:
            modules = []
        for module in modules:
            if module in NETWORK_IMPORTS:
                findings.add(f"network_import:{module}")
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in DYNAMIC_CALLS:
                findings.add(f"dynamic_execution:{name}")
            if name and name.split(".", 1)[0] in PROCESS_MODULES:
                findings.add(f"process_execution:{name}")
            if name in {"os.popen", "os.system"}:
                findings.add(f"process_execution:{name}")
    return {
        "path": _relative(path, root),
        "parsed": True,
        "executed": False,
        "findings": sorted(findings),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def audit_onnx_graphs(snapshot: Path, *, load_model: Any) -> dict[str, Any]:
    """Parse ONNX protobuf graphs without loading external tensor data."""
    snapshot = snapshot.resolve()
    models = []
    operator_counts: dict[tuple[str, str], int] = {}
    opsets: dict[tuple[str, int], None] = {}
    external_data_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    parse_failures = []
    for path in sorted(snapshot.rglob("*.onnx")):
        relative = _relative(path, snapshot)
        try:
            model = load_model(str(path), load_external_data=False)
        except Exception as error:
            parse_failures.append(f"{relative}:{type(error).__name__}")
            continue
        node_count = 0
        for node in model.graph.node:
            domain = node.domain or "ai.onnx"
            key = (domain, node.op_type)
            operator_counts[key] = operator_counts.get(key, 0) + 1
            node_count += 1
        for row in model.opset_import:
            opsets[(row.domain or "ai.onnx", int(row.version))] = None
        for tensor in model.graph.initializer:
            for entry in getattr(tensor, "external_data", []):
                if entry.key != "location":
                    continue
                location = entry.value
                location_path = PurePosixPath(location)
                safe = (
                    not location_path.is_absolute()
                    and location_path.parts
                    and all(
                        part not in {"", ".", ".."}
                        for part in location_path.parts
                    )
                )
                target = path.parent / location if safe else None
                external_data_by_key[(relative, location)] = {
                    "model": relative,
                    "location": location,
                    "safe_relative": bool(safe),
                    "exists": bool(target and target.is_file()),
                }
        models.append({"path": relative, "node_count": node_count})
    return {
        "status": "blocked_parse_failure" if parse_failures else "inventoried",
        "model_count": len(models),
        "models": models,
        "operators": [
            {"domain": domain, "op_type": op_type, "count": count}
            for (domain, op_type), count in sorted(operator_counts.items())
        ],
        "opsets": [
            {"domain": domain, "version": version}
            for domain, version in sorted(opsets)
        ],
        "external_data": [
            external_data_by_key[key] for key in sorted(external_data_by_key)
        ],
        "parse_failures": parse_failures,
        "runtime_effects": {
            "loaded_external_tensor_data": False,
            "created_inference_session": False,
            "executed_graph": False,
            "used_gpu": False,
        },
    }


def _declared_license(snapshot: Path) -> str | None:
    readme = snapshot / "README.md"
    if not readme.is_file():
        return None
    match = re.search(
        r"(?im)^\s*license\s*:\s*['\"]?([a-z0-9_.+-]+)",
        readme.read_text(errors="replace"),
    )
    return match.group(1).lower() if match else None


def _requirements(snapshot: Path) -> list[str]:
    path = snapshot / "requirements.txt"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(errors="replace").splitlines():
        value = line.split("#", 1)[0].strip()
        if value:
            rows.append(value)
    return rows


def _manifest_audit(snapshot: Path) -> dict[str, Any]:
    manifests = []
    missing_files = []
    malformed = []
    for path in sorted(snapshot.glob("*/manifest.json")):
        relative = _relative(path, snapshot)
        try:
            payload = json.loads(path.read_text())
            sub_models = payload["sub_models"]
            if not isinstance(sub_models, dict):
                raise TypeError("sub_models_not_object")
            referenced = []
            for row in sub_models.values():
                filename = row["filename"]
                if not isinstance(filename, str):
                    raise TypeError("filename_not_string")
                candidate = path.parent / filename
                referenced.append(_relative(candidate, snapshot))
                if not candidate.is_file():
                    missing_files.append(_relative(candidate, snapshot))
            manifests.append(
                {
                    "path": relative,
                    "device": payload.get("device"),
                    "precision": payload.get("precision"),
                    "execution_provider": payload.get("execution_provider"),
                    "referenced_files": sorted(referenced),
                }
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            malformed.append(f"{relative}:{type(error).__name__}")
    return {
        "manifests": manifests,
        "missing_files": sorted(set(missing_files)),
        "malformed": malformed,
    }


def audit_snapshot(
    snapshot: Path,
    *,
    repository: str,
    revision: str,
    expected_size_bytes: int | None,
    hash_files: bool,
    onnx_loader: Any | None = None,
) -> dict[str, Any]:
    snapshot = snapshot.resolve()
    entries = sorted(snapshot.rglob("*"))
    symlinks = [_relative(path, snapshot) for path in entries if path.is_symlink()]
    files = [
        path for path in entries if path.is_file() and not path.is_symlink()
    ]
    incomplete = [
        _relative(path, snapshot)
        for path in files
        if path.name.endswith(".incomplete")
    ]
    total_size = sum(path.stat().st_size for path in files)
    variants = sorted(
        path.name
        for path in snapshot.iterdir()
        if path.is_dir() and path.name in EXPECTED_VARIANTS
    )

    manifest_audit = _manifest_audit(snapshot)
    onnx_audit = (
        audit_onnx_graphs(snapshot, load_model=onnx_loader)
        if onnx_loader is not None
        else {
            "status": "not_run",
            "model_count": 0,
            "models": [],
            "operators": [],
            "opsets": [],
            "external_data": [],
            "parse_failures": [],
            "runtime_effects": {
                "loaded_external_tensor_data": False,
                "created_inference_session": False,
                "executed_graph": False,
                "used_gpu": False,
            },
        }
    )
    python_audit = [
        audit_python_source(path, snapshot)
        for path in files
        if path.suffix == ".py"
    ]
    standalone_license = next(
        (name for name in LICENSE_NAMES if (snapshot / name).is_file()), None
    )
    declared_license = _declared_license(snapshot)

    blockers = []
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        blockers.append("revision_not_immutable")
    if standalone_license is None:
        blockers.append("standalone_license_file_missing")
    if incomplete:
        blockers.append("incomplete_files_present")
    if symlinks:
        blockers.append("symlinks_present")
    if set(variants) != EXPECTED_VARIANTS:
        blockers.append("variant_set_incomplete")
    if manifest_audit["missing_files"]:
        blockers.append("manifest_references_missing_files")
    if manifest_audit["malformed"]:
        blockers.append("manifest_malformed")
    if onnx_audit["status"] == "blocked_parse_failure":
        blockers.append("onnx_parse_failure")
    if any(
        not row["safe_relative"] or not row["exists"]
        for row in onnx_audit["external_data"]
    ):
        blockers.append("onnx_external_data_invalid")
    if any(row["findings"] for row in python_audit):
        blockers.append("python_dangerous_primitives_present")
    size_matches = (
        None
        if expected_size_bytes is None
        else total_size == expected_size_bytes
    )
    if size_matches is False:
        blockers.append("snapshot_size_mismatch")

    hashes = []
    if hash_files:
        hashes = [
            {
                "path": _relative(path, snapshot),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ]

    return {
        "schema": "agent_bridge.voice_snapshot_static_audit.v1",
        "status": "blocked" if blockers else "static_audit_passed",
        "repository": repository,
        "revision": revision,
        "snapshot": str(snapshot),
        "inventory": {
            "file_count": len(files),
            "total_size_bytes": total_size,
            "variant_count": len(variants),
            "variants": variants,
            "incomplete_files": incomplete,
            "symlinks": symlinks,
        },
        "integrity": {
            "expected_size_bytes": expected_size_bytes,
            "size_matches": size_matches,
            "file_hashes": hashes,
        },
        "license_audit": {
            "declared": declared_license,
            "standalone_file": standalone_license,
            "status": (
                "standalone_file_present"
                if standalone_license
                else "declaration_only"
            ),
        },
        "requirements": _requirements(snapshot),
        "manifest_audit": manifest_audit,
        "onnx_audit": onnx_audit,
        "python_audit": python_audit,
        "blockers": blockers,
        "runtime_effects": {
            "imported_community_code": False,
            "loaded_onnx": False,
            "installed_dependencies": False,
            "used_gpu": False,
            "rendered_audio": False,
            "played_audio": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Statically audit a voice-model snapshot without loading it"
    )
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--expected-size-bytes", type=int)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--no-hashes", action="store_true")
    parser.add_argument(
        "--onnx-inventory",
        action="store_true",
        help="Parse ONNX protobuf graphs without loading external tensor data",
    )
    args = parser.parse_args()

    onnx_loader = None
    if args.onnx_inventory:
        import onnx

        onnx_loader = onnx.load_model
    receipt = audit_snapshot(
        args.snapshot,
        repository=args.repository,
        revision=args.revision,
        expected_size_bytes=args.expected_size_bytes,
        hash_files=not args.no_hashes,
        onnx_loader=onnx_loader,
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["status"] == "static_audit_passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
