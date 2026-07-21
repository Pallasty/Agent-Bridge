#!/usr/bin/env python3
"""Offline verifier for the bounded, partial P11-E1 source-archive result."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path("/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e1-source-custody")
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "majorana_certificate_p11e1_source_archive_custody_manifest.json"
REPORT = HERE / "majorana_certificate_p11e1_source_archive_custody_report.json"
OUTCOME = "PARTIAL_VERIFIED_SOURCE_ARCHIVES_RETAINED_COMPLETE_SET_CUSTODY_NOT_ESTABLISHED"
EXPECTED = {
    "gcc-15": "15.2.0-16ubuntu1",
    "binutils": "2.46-3ubuntu2",
    "linux": "7.0.0-28.28",
    "linux-signed": "7.0.0-28.28",
}


class VerificationError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")


def load(path: Path) -> Any:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"invalid JSON: {path}") from exc
    if canonical(value) != raw:
        raise VerificationError(f"noncanonical JSON: {path}")
    return value


def sha256(path: Path) -> tuple[int, str]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"not a regular file: {path}")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def check_file(root: Path, row: dict[str, Any]) -> None:
    relative = row["relative_path"]
    path = root / relative
    if path.resolve().parent != (root / Path(relative).parent).resolve() or ".." in Path(relative).parts:
        raise VerificationError(f"unsafe receipt path: {relative}")
    if sha256(path) != (row["size_bytes"], row["sha256"]):
        raise VerificationError(f"digest mismatch: {relative}")


def verify() -> dict[str, Any]:
    manifest = load(MANIFEST)
    report = load(REPORT)
    state = load(ROOT / "receipts/state.json")
    if manifest["outcome"] != OUTCOME or report["outcome"] != OUTCOME or state["outcome"] != OUTCOME:
        raise VerificationError("partial outcome is not consistently recorded")
    if state["snapshot_id"] != "20260719T064131Z" or state["complete_set_custody_established"]:
        raise VerificationError("snapshot or complete-custody claim drift")
    actual = {row["source_package"]: row for row in state["packages"]}
    if set(actual) != {"gcc-15", "binutils"}:
        raise VerificationError("accepted package set must be exactly gcc-15 and binutils")
    accepted = []
    for package, version in (("gcc-15", EXPECTED["gcc-15"]), ("binutils", EXPECTED["binutils"] )):
        receipt = actual[package]
        if receipt["source_version"] != version or len(receipt["attempts"]) not in (1, 2):
            raise VerificationError(f"invalid receipt identity: {package}")
        for attempt in receipt["attempts"]:
            for stream in ("stdout", "stderr"):
                check_file(ROOT, attempt[stream])
        accepted_dir = receipt["accepted_relative_path"]
        for file_row in receipt["files"]:
            observed = {"relative_path": f"{accepted_dir}/{file_row['filename']}", "size_bytes": file_row["size_bytes"], "sha256": file_row["sha256"]}
            check_file(ROOT, observed)
            if not file_row["relative_path"].startswith("incoming/"):
                raise VerificationError("expected stale pre-rename receipt path was not preserved")
            accepted.append(observed)
    commands = {row["step_id"]: [] for row in state["commands"]}
    for row in state["commands"]:
        commands[row["step_id"]].append(row)
        for stream in ("stdout", "stderr"):
            check_file(ROOT, row[stream])
    if [x["returncode"] for x in commands.get("APT_SOURCE_LINUX", [])] != [100, 100]:
        raise VerificationError("linux retry exhaustion not evidenced")
    if "APT_SOURCE_LINUX_SIGNED" in commands:
        raise VerificationError("linux-signed must not run after linux exhaustion")
    for row in state["index_files"]:
        check_file(ROOT, row)
    if manifest["state_sha256"] != sha256(ROOT / "receipts/state.json")[1]:
        raise VerificationError("state digest mismatch")
    if manifest["accepted_files"] != accepted:
        raise VerificationError("manifest accepted-file receipt mismatch")
    if report["accepted_source_packages"] != ["binutils=2.46-3ubuntu2", "gcc-15=15.2.0-16ubuntu1"]:
        raise VerificationError("report accepted identity mismatch")
    if report["unattempted_source_packages"] != ["linux-signed=7.0.0-28.28"]:
        raise VerificationError("report stop rule mismatch")
    return {"accepted_file_count": len(accepted), "outcome": OUTCOME, "status": "PASS"}


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        print(canonical(verify()).decode("ascii"))
    except (OSError, KeyError, TypeError, VerificationError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
