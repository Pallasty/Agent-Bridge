#!/usr/bin/env python3
"""Bounded P11-E1 source archive acquisition runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
ROOT = Path("/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e1-source-custody")
SNAPSHOT = "20260719T064131Z"
APT_GET = Path("/usr/bin/apt-get")
KEYRING = Path("/usr/share/keyrings/ubuntu-archive-keyring.gpg")
IDENTITIES = [
    ("gcc-15", "15.2.0-16ubuntu1"),
    ("binutils", "2.46-3ubuntu2"),
    ("linux", "7.0.0-28.28"),
    ("linux-signed", "7.0.0-28.28"),
]
SOURCES = f"""Types: deb-src
URIs: https://archive.ubuntu.com/ubuntu/
Suites: resolute resolute-updates
Components: main restricted universe multiverse
Signed-By: {KEYRING}
Snapshot: {SNAPSHOT}

Types: deb-src
URIs: https://security.ubuntu.com/ubuntu/
Suites: resolute-security
Components: main restricted universe multiverse
Signed-By: {KEYRING}
Snapshot: {SNAPSHOT}
"""
APT_CONF_LINES = [
    f'Dir::Etc::SourceList "{ROOT}/apt/ubuntu.sources";',
    'Dir::Etc::SourceParts "-";',
    'Dir::Etc::Parts "-";',
    'Dir::Etc::main "-";',
    f'Dir::State::Lists "{ROOT}/apt/lists";',
    f'Dir::State::status "{ROOT}/apt/empty-status";',
    f'Dir::Cache::archives "{ROOT}/apt/archives";',
    'Dir::Cache::pkgcache "";',
    'Dir::Cache::srcpkgcache "";',
    'APT::Get::List-Cleanup "false";',
    'APT::Get::Download-Only "true";',
    'APT::Get::Only-Source "true";',
    'Acquire::AllowInsecureRepositories "false";',
    'Acquire::AllowDowngradeToInsecureRepositories "false";',
    'Acquire::Check-Valid-Until "true";',
    'Acquire::Languages "none";',
    'Acquire::Retries "0";',
]


class AcquisitionError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")


def digest(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise AcquisitionError(f"not a regular file: {path}")
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            h.update(chunk)
    try:
        identity = {"relative_path": str(path.relative_to(ROOT))}
    except ValueError:
        identity = {"absolute_path": str(path)}
    return {**identity, "size_bytes": size, "sha256": h.hexdigest()}


def parse_control(raw: bytes) -> dict[str, str]:
    text = raw.decode("utf-8")
    if text.startswith("-----BEGIN PGP SIGNED MESSAGE-----"):
        marker = "\n\n"
        pos = text.find(marker)
        if pos < 0:
            raise AcquisitionError("malformed clearsigned dsc")
        text = text[pos + len(marker):]
        end = text.find("\n-----BEGIN PGP SIGNATURE-----")
        if end < 0:
            raise AcquisitionError("missing dsc signature trailer")
        text = text[:end].replace("\n- -", "\n-")
    fields: dict[str, str] = {}
    key: str | None = None
    for line in text.splitlines():
        if line.startswith((" ", "\t")):
            if key is None:
                raise AcquisitionError("orphan continuation")
            fields[key] += "\n" + line[1:]
        elif ":" in line:
            key, value = line.split(":", 1)
            if key in fields:
                raise AcquisitionError(f"duplicate field: {key}")
            fields[key] = value.lstrip()
        elif line:
            raise AcquisitionError("malformed control line")
    return fields


def checksum_rows(value: str) -> dict[str, tuple[int, str]]:
    rows: dict[str, tuple[int, str]] = {}
    for line in value.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 3:
            raise AcquisitionError("malformed Checksums-Sha256 row")
        sha, size_text, name = parts
        if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
            raise AcquisitionError("invalid sha256")
        if name != Path(name).name or name in (".", "..") or "/" in name or "\\" in name or name in rows:
            raise AcquisitionError("unsafe or duplicate filename")
        rows[name] = (int(size_text), sha)
    return rows


def verify_download(directory: Path, package: str, version: str) -> tuple[list[dict[str, Any]], str]:
    dscs = list(directory.glob("*.dsc"))
    if len(dscs) != 1:
        raise AcquisitionError("expected exactly one dsc")
    dsc = dscs[0]
    fields = parse_control(dsc.read_bytes())
    if fields.get("Source", fields.get("Package")) != package or fields.get("Version") != version:
        raise AcquisitionError("dsc identity mismatch")
    rows = checksum_rows(fields.get("Checksums-Sha256", ""))
    expected = set(rows) | {dsc.name}
    actual = {p.name for p in directory.iterdir() if p.is_file() and not p.is_symlink()}
    if actual != expected:
        raise AcquisitionError(f"archive set mismatch: expected={sorted(expected)} actual={sorted(actual)}")
    receipts = []
    for path in sorted(directory.iterdir(), key=lambda p: p.name):
        row = digest(path)
        row["filename"] = path.name
        if path.name in rows and (row["size_bytes"], row["sha256"]) != rows[path.name]:
            raise AcquisitionError(f"dsc checksum mismatch: {path.name}")
        receipts.append(row)
    return receipts, dsc.name


def safe_environment() -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(ROOT),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "APT_CONFIG": str(ROOT / "apt/apt.conf"),
    }


def run_command(step_id: str, argv: list[str], cwd: Path, attempt: int) -> dict[str, Any]:
    result = subprocess.run(argv, cwd=cwd, env=safe_environment(), capture_output=True, check=False)
    logs = ROOT / "receipts/logs"
    logs.mkdir(parents=True, exist_ok=True)
    out = logs / f"{step_id}.attempt-{attempt}.stdout"
    err = logs / f"{step_id}.attempt-{attempt}.stderr"
    out.write_bytes(result.stdout)
    err.write_bytes(result.stderr)
    return {
        "step_id": step_id,
        "attempt": attempt,
        "argv": argv,
        "cwd": str(cwd),
        "environment_keys": sorted(safe_environment()),
        "returncode": result.returncode,
        "stdout": digest(out),
        "stderr": digest(err),
    }


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(canonical_bytes(value))


def setup() -> None:
    if ROOT.exists() or ROOT.is_symlink():
        if ROOT.is_symlink() or not ROOT.is_dir():
            raise AcquisitionError("existing custody root is invalid")
        expected_sources = ROOT / "apt/ubuntu.sources"
        expected_config = ROOT / "apt/apt.conf"
        if not expected_sources.is_file() or expected_sources.read_text(encoding="utf-8") != SOURCES:
            raise AcquisitionError("existing source template drift")
        if not expected_config.is_file() or expected_config.read_text(encoding="utf-8") != "\n".join(APT_CONF_LINES) + "\n":
            raise AcquisitionError("existing APT config drift")
        if (ROOT / "receipts/state.json").exists() or any((ROOT / "accepted").iterdir()) or any((ROOT / "incoming").iterdir()):
            raise AcquisitionError("existing custody root is not pristine resumable state")
        return
    for path in (ROOT / "apt/lists/partial", ROOT / "apt/archives/partial", ROOT / "incoming", ROOT / "accepted", ROOT / "receipts/logs"):
        path.mkdir(parents=True, mode=0o700, exist_ok=False if path == ROOT else True)
    (ROOT / "apt/empty-status").write_bytes(b"")
    (ROOT / "apt/ubuntu.sources").write_text(SOURCES, encoding="utf-8")
    (ROOT / "apt/apt.conf").write_text("\n".join(APT_CONF_LINES) + "\n", encoding="utf-8")


def execute() -> dict[str, Any]:
    setup()
    state: dict[str, Any] = {
        "schema_version": 1,
        "snapshot_id": SNAPSHOT,
        "custody_root": str(ROOT),
        "apt_get": digest(APT_GET),
        "ubuntu_archive_keyring": digest(KEYRING),
        "apt_config": digest(ROOT / "apt/apt.conf"),
        "deb822_sources": digest(ROOT / "apt/ubuntu.sources"),
        "commands": [],
        "packages": [],
        "complete_set_custody_established": False,
    }
    update = run_command("APT_UPDATE_ISOLATED_SNAPSHOT", [str(APT_GET), "--snapshot", SNAPSHOT, "update"], ROOT, 1)
    state["commands"].append(update)
    if update["returncode"] != 0:
        state["outcome"] = "CLOSED_SNAPSHOT_OR_EXACT_SOURCE_VERSION_UNAVAILABLE"
        write_json(ROOT / "receipts/state.json", state)
        return state
    state["index_files"] = [digest(p) for p in sorted((ROOT / "apt/lists").iterdir()) if p.is_file() and not p.is_symlink()]
    for package, version in IDENTITIES:
        accepted = False
        attempts = []
        for attempt in (1, 2):
            incoming = ROOT / "incoming" / f"{package}.attempt-{attempt}"
            incoming.mkdir(mode=0o700)
            argv = [str(APT_GET), "--snapshot", SNAPSHOT, "--download-only", "--only-source", "source", f"{package}={version}"]
            command = run_command(f"APT_SOURCE_{package.upper().replace('-', '_')}", argv, incoming, attempt)
            state["commands"].append(command)
            attempts.append(command)
            if command["returncode"] == 0:
                try:
                    files, dsc = verify_download(incoming, package, version)
                    target = ROOT / "accepted" / f"{package}={version}"
                    incoming.rename(target)
                    receipt = {"source_package": package, "source_version": version, "snapshot_id": SNAPSHOT,
                               "dsc_filename": dsc, "files": files, "attempts": attempts, "accepted_relative_path": str(target.relative_to(ROOT))}
                    write_json(ROOT / "receipts" / f"{package}.json", receipt)
                    state["packages"].append(receipt)
                    accepted = True
                    break
                except Exception as error:
                    command["verification_error"] = str(error)
            shutil.rmtree(incoming)
        if not accepted:
            state["outcome"] = "PARTIAL_VERIFIED_SOURCE_ARCHIVES_RETAINED_COMPLETE_SET_CUSTODY_NOT_ESTABLISHED" if state["packages"] else "CLOSED_SNAPSHOT_OR_EXACT_SOURCE_VERSION_UNAVAILABLE"
            write_json(ROOT / "receipts/state.json", state)
            return state
    state["complete_set_custody_established"] = True
    state["outcome"] = "SOURCE_ARCHIVE_CUSTODY_ESTABLISHED_EXACT_FOUR_PACKAGE_SET"
    write_json(ROOT / "receipts/state.json", state)
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("choose --execute")
    try:
        state = execute()
    except Exception as error:
        print(json.dumps({"status": "FATAL_PREFLIGHT_OR_RUNNER_ERROR", "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps({"outcome": state["outcome"], "accepted_packages": len(state["packages"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
