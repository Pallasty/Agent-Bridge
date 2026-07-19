#!/usr/bin/env python3
"""Bounded, fail-closed RustSec scan for the frozen G2C Wasmtime lock graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, raw: str) -> "Version":
        if "+" in raw or "-" in raw:
            raise ValueError(f"pre-release/build metadata is outside scanner grammar: {raw}")
        parts = raw.split(".")
        if not 1 <= len(parts) <= 3 or any(not part.isdigit() for part in parts):
            raise ValueError(f"unsupported semantic version: {raw}")
        numbers = [int(part) for part in parts]
        numbers.extend([0] * (3 - len(numbers)))
        return cls(*numbers)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_lock(lock_path: Path) -> tuple[dict[str, list[str]], int, int]:
    text = lock_path.read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^\[\[package\]\]\s*$", text)[1:]
    versions: dict[str, set[str]] = {}
    registry_count = 0
    for block in blocks:
        name = re.search(r'(?m)^name = "([^"]+)"$', block)
        version = re.search(r'(?m)^version = "([^"]+)"$', block)
        if not name or not version:
            raise ValueError("Cargo.lock package row is missing name or version")
        package_name = name.group(1)
        package_version = version.group(1)
        versions.setdefault(package_name, set()).add(package_version)
        if re.search(r'(?m)^source = "registry\+', block):
            registry_count += 1
            if not re.search(r'(?m)^checksum = "[0-9a-f]{64}"$', block):
                raise ValueError(f"registry package lacks checksum: {package_name}")
    return (
        {name: sorted(package_versions) for name, package_versions in versions.items()},
        len(blocks),
        registry_count,
    )


def caret_bounds(raw: str) -> tuple[Version, Version]:
    lower = Version.parse(raw)
    if lower.major > 0:
        upper = Version(lower.major + 1, 0, 0)
    elif lower.minor > 0:
        upper = Version(0, lower.minor + 1, 0)
    else:
        upper = Version(0, 0, lower.patch + 1)
    return lower, upper


def comparator_matches(version: Version, raw: str) -> bool:
    value = raw.strip()
    if value.startswith("^"):
        lower, upper = caret_bounds(value[1:].strip())
        return lower <= version < upper
    match = re.fullmatch(r"(>=|<=|>|<|=)?\s*(\d+(?:\.\d+){0,2})", value)
    if not match:
        raise ValueError(f"unsupported RustSec requirement comparator: {raw}")
    operator = match.group(1) or "="
    bound = Version.parse(match.group(2))
    return {
        "=": version == bound,
        ">=": version >= bound,
        "<=": version <= bound,
        ">": version > bound,
        "<": version < bound,
    }[operator]


def requirement_matches(version: Version, raw: str) -> bool:
    return all(comparator_matches(version, part) for part in raw.split(","))


def extract_array(section: str, key: str) -> list[str] | None:
    match = re.search(rf"(?ms)^{re.escape(key)}\s*=\s*\[(.*?)\]", section)
    if not match:
        return None
    residue = re.sub(r'"[^"]*"|[\s,]', "", match.group(1))
    if residue:
        raise ValueError(f"unsupported syntax in versions.{key}: {residue}")
    return re.findall(r'"([^"]+)"', match.group(1))


def advisory_row(path: Path, package_version: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    front = re.search(r"(?ms)```toml\s*(.*?)```", text)
    if not front:
        raise ValueError(f"missing TOML front matter: {path}")
    toml = front.group(1)
    advisory_id = re.search(r'(?m)^id\s*=\s*"([^"]+)"$', toml)
    package = re.search(r'(?m)^package\s*=\s*"([^"]+)"$', toml)
    versions_section = re.search(r"(?ms)^\[versions\]\s*(.*?)(?=^\[|\Z)", toml)
    if not advisory_id or not package or not versions_section:
        raise ValueError(f"incomplete advisory front matter: {path}")
    withdrawn = bool(re.search(r"(?m)^withdrawn\s*=", toml))
    informational = re.search(r'(?m)^informational\s*=\s*"([^"]+)"$', toml)
    patched = extract_array(versions_section.group(1), "patched")
    unaffected = extract_array(versions_section.group(1), "unaffected")
    if patched is None and unaffected is None:
        raise ValueError("versions section has neither patched nor unaffected array")
    patched = patched or []
    unaffected = unaffected or []
    version = Version.parse(package_version)
    safe_ranges = patched + unaffected
    safe = any(requirement_matches(version, requirement) for requirement in safe_ranges)
    if withdrawn:
        status = "withdrawn"
    elif safe:
        status = "patched_or_unaffected"
    elif informational:
        status = "informational_finding"
    else:
        status = "vulnerability"
    return {
        "id": advisory_id.group(1),
        "package": package.group(1),
        "version": package_version,
        "status": status,
        "informational": informational.group(1) if informational else None,
        "patched": patched,
        "unaffected": unaffected,
        "source_path": str(path.relative_to(path.parents[2])),
    }


def git_value(db_path: Path, *args: str) -> str:
    completed = subprocess.run(
        ["/usr/bin/git", "-C", str(db_path), *args],
        check=True,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    return completed.stdout.strip()


def build_receipt(lock_path: Path, db_path: Path) -> dict[str, Any]:
    package_versions, package_count, registry_count = parse_lock(lock_path)
    worktree_clean = git_value(db_path, "status", "--porcelain=v1", "--untracked-files=all") == ""
    rows: list[dict[str, Any]] = []
    parse_errors: list[dict[str, str]] = []
    all_advisories = sorted((db_path / "crates").glob("*/*.md"))
    matched_paths: set[str] = set()
    for package, versions in sorted(package_versions.items()):
        package_dir = db_path / "crates" / package
        if not package_dir.is_dir():
            continue
        for path in sorted(package_dir.glob("*.md")):
            matched_paths.add(str(path.relative_to(db_path)))
            for version in versions:
                try:
                    row = advisory_row(path, version)
                    if row["package"] != package:
                        raise ValueError(
                            f"advisory package mismatch: directory={package} metadata={row['package']}"
                        )
                    rows.append(row)
                except ValueError as exc:
                    parse_errors.append(
                        {
                            "path": str(path.relative_to(db_path)),
                            "package": package,
                            "version": version,
                            "error": str(exc),
                        }
                    )
    counts = {
        status: sum(row["status"] == status for row in rows)
        for status in ("patched_or_unaffected", "withdrawn", "informational_finding", "vulnerability")
    }
    return {
        "schema": "agent_bridge.engram_g14_wasi_g2c_rustsec_scan_receipt.v0",
        "scanner": {
            "id": "g2c_stdlib_rustsec_exact_lock_v0",
            "grammar": "numeric_semver_comparators_and_caret_no_prerelease_or_build_metadata",
            "unknown_syntax": "FAIL_CLOSED_PARSE_ERROR",
            "cargo_audit_executed": False,
            "official_cargo_audit_receipt_claimed": False,
        },
        "database": {
            "repository": "https://github.com/RustSec/advisory-db",
            "origin_url": git_value(db_path, "remote", "get-url", "origin"),
            "commit": git_value(db_path, "rev-parse", "HEAD"),
            "tree": git_value(db_path, "rev-parse", "HEAD^{tree}"),
            "commit_timestamp": git_value(db_path, "show", "-s", "--format=%cI", "HEAD"),
            "crate_advisory_file_count": len(all_advisories),
            "worktree_clean": worktree_clean,
        },
        "lockfile": {
            "sha256": sha256(lock_path),
            "package_instances": package_count,
            "registry_package_instances": registry_count,
        },
        "result": {
            "matched_advisory_files_unique": len(matched_paths),
            "evaluated_package_advisory_pairs": len(rows) + len(parse_errors),
            "parse_error_count": len(parse_errors),
            "status_counts": counts,
            "accepted_equivalent_static_scan_pass": worktree_clean
            and not parse_errors
            and counts["vulnerability"] == 0
            and counts["informational_finding"] == 0,
            "dependency_promotion_authority": False,
        },
        "parse_errors": parse_errors,
        "advisories": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = build_receipt(args.lock.resolve(), args.db.resolve())
    encoded = json.dumps(receipt, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if receipt["result"]["accepted_equivalent_static_scan_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
