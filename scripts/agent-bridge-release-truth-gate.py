#!/usr/bin/env python3
"""Inspect Agent-Bridge release identity and documentation truth.

This gate is read-only. It compares source tags, CHANGELOG releases, Cargo and
binary version sources, source-only distribution policy, embedding dimensions,
and an optional cargo-fmt check. It does not select a version, create a tag,
publish a release, format files, or modify repository state.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.release_truth_gate.v0"
VERSION_TAG_RE = re.compile(r"^v(?P<version>\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)$")
CHANGELOG_RELEASE_RE = re.compile(r"^## \[(?P<version>\d+\.\d+\.\d+)\]", re.MULTILINE)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def run(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        fail(f"command failed ({completed.returncode}): {' '.join(args)}: {detail}")
    return completed


def git_text(repo: Path, *args: str) -> str:
    return run(["git", *args], cwd=repo).stdout.strip()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"failed to read {path}: {exc}")


def load_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(read_text(path))
    except tomllib.TOMLDecodeError as exc:
        fail(f"failed to parse {path}: {exc}")


def latest_version_tag(repo: Path) -> str:
    output = git_text(repo, "tag", "--list", "v[0-9]*", "--sort=-version:refname")
    for line in output.splitlines():
        tag = line.strip()
        if VERSION_TAG_RE.fullmatch(tag):
            return tag
    fail("no semantic v* source marker found")


def workspace_member_version_inheritance(repo: Path, root_toml: dict[str, Any]) -> dict[str, bool]:
    results: dict[str, bool] = {}
    for member in root_toml["workspace"]["members"]:
        package = load_toml(repo / member / "Cargo.toml").get("package", {})
        version = package.get("version")
        results[member] = isinstance(version, dict) and version.get("workspace") is True
    return dict(sorted(results.items()))


def inspect_format(repo: Path, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {
            "checked": False,
            "passed": None,
            "diff_file_count": None,
            "captured_output_bytes": 0,
        }

    completed = run(["cargo", "fmt", "--all", "--", "--check"], cwd=repo, check=False)
    output = completed.stdout + completed.stderr
    diff_files = sorted(set(re.findall(r"^Diff in (.+?):\d+:$", output, re.MULTILINE)))
    return {
        "checked": True,
        "passed": completed.returncode == 0,
        "diff_file_count": len(diff_files),
        "captured_output_bytes": len(output.encode("utf-8")),
    }


def inspect_binary(repo: Path, binary: str | None) -> dict[str, Any]:
    if binary is None:
        return {
            "checked": False,
            "path": None,
            "version_output": None,
            "parsed_version": None,
        }

    path = Path(binary).expanduser()
    if not path.is_absolute():
        path = repo / path
    if not path.is_file():
        fail(f"binary not found: {path}")
    completed = run([str(path), "--version"], cwd=repo)
    output = completed.stdout.strip()
    match = re.search(r"(?P<version>\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)$", output)
    if match is None:
        fail(f"unable to parse binary version output: {output!r}")
    return {
        "checked": True,
        "path": str(path),
        "version_output": output,
        "parsed_version": match.group("version"),
    }


def build_gate(repo: Path, *, binary: str | None, check_fmt: bool) -> dict[str, Any]:
    repo = repo.resolve()
    if not (repo / ".git").exists():
        git_dir = run(["git", "rev-parse", "--git-dir"], cwd=repo, check=False)
        if git_dir.returncode != 0:
            fail(f"not a Git repository: {repo}")

    root_toml = load_toml(repo / "Cargo.toml")
    workspace_version = str(root_toml["workspace"]["package"]["version"])
    member_inheritance = workspace_member_version_inheritance(repo, root_toml)
    bridge_toml = load_toml(repo / "crates" / "bridge" / "Cargo.toml")

    tag = latest_version_tag(repo)
    tag_match = VERSION_TAG_RE.fullmatch(tag)
    if tag_match is None:
        fail(f"invalid latest version tag: {tag}")
    tag_version = tag_match.group("version")
    head = git_text(repo, "rev-parse", "HEAD")
    tag_commit = git_text(repo, "rev-list", "-n", "1", tag)
    commits_since_tag = int(git_text(repo, "rev-list", "--count", f"{tag}..HEAD"))
    tag_date = git_text(repo, "show", "-s", "--format=%cI", f"{tag}^{{}}")

    changelog = read_text(repo / "CHANGELOG.md")
    changelog_versions = CHANGELOG_RELEASE_RE.findall(changelog)
    if not changelog_versions:
        fail("CHANGELOG has no semantic release heading")
    changelog_latest = changelog_versions[0]

    readme = read_text(repo / "README.md")
    gitlab_ci = read_text(repo / ".gitlab-ci.yml")
    vector_source = read_text(repo / "crates" / "store" / "src" / "vector.rs")
    bridge_source = read_text(repo / "crates" / "bridge" / "src" / "main.rs")
    mcp_source = read_text(repo / "crates" / "bridge" / "src" / "mcp_tools.rs")
    bridge_manifest = read_text(repo / "crates" / "bridge" / "Cargo.toml")
    sync_doc = read_text(repo / "docs" / "CROSS-MACHINE-SYNC.md")

    source_only_checks = {
        "readme_source_only": "distributed as **source only**" in readme,
        "changelog_source_only": "Distribution policy: source only" in changelog,
        "github_release_workflow_absent": not (repo / ".github" / "workflows" / "release.yml").exists(),
        "gitlab_release_pipeline_absent": (
            "ships SOURCE ONLY" in gitlab_ci
            and "no release pipelines" in gitlab_ci
            and "Version tags (v*) are source markers" in gitlab_ci
        ),
        "bridge_feature_comment_source_only": (
            "Source builds enable `onnx-embed` by default" in bridge_manifest
            and "Prebuilt release binaries are built" not in bridge_manifest
        ),
    }

    runtime_embedding_checks = {
        "gte_maps_to_768": (
            '"gte-multilingual-base" => 768' in vector_source
            and "_ => 384" in vector_source
        ),
        "compiled_default_is_gte": (
            "Compiled default is now gte-multilingual-base (768-dim multilingual)"
            in vector_source
        ),
        "hash_fallback_is_384": "FNV-1a feature-hash embedding: 384-dim" in vector_source,
    }
    embedding_doc_checks = {
        "readme_model_aware": (
            "model-aware local embedding" in readme
            and re.search(
                r"compiled default is\s+`gte-multilingual-base` at 768 dimensions",
                readme,
            )
            is not None
            and re.search(r"deterministic 384-dim\s+`fnv1a-hash-384`", readme)
            is not None
        ),
        "sync_doc_model_aware": (
            "dimension matches the active" in sync_doc
            and "`gte-multilingual-base` at 768 dimensions" in sync_doc
        ),
        "vector_api_model_aware": (
            "Compute a model-aware f32 embedding" in vector_source
            and "Compute a 384-dim f32 embedding" not in vector_source
        ),
        "stale_fixed_384_claims_removed": (
            "Memories get a **384-dim embedding**" not in readme
            and "Each `memory_save` writes a 384-dim embedding" not in sync_doc
        ),
    }

    bridge_package = bridge_toml["package"]
    bridge_inherits_workspace_version = (
        isinstance(bridge_package.get("version"), dict)
        and bridge_package["version"].get("workspace") is True
    )
    binary_declared = any(
        item.get("name") == "agent-bridge" and item.get("path") == "src/main.rs"
        for item in bridge_toml.get("bin", [])
    )
    cli_uses_cargo_version = "#[command(version," in bridge_source
    mcp_uses_cargo_version = 'env!("CARGO_PKG_VERSION")' in bridge_source
    capability_uses_cargo_version = 'let version = env!("CARGO_PKG_VERSION");' in mcp_source

    binary_observation = inspect_binary(repo, binary)
    observed_binary_matches_cargo = (
        not binary_observation["checked"]
        or binary_observation["parsed_version"] == workspace_version
    )

    version_gates = {
        "latest_tag_matches_changelog": tag_version == changelog_latest,
        "workspace_members_inherit_version": all(member_inheritance.values()),
        "bridge_inherits_workspace_version": bridge_inherits_workspace_version,
        "agent_bridge_binary_declared": binary_declared,
        "cli_uses_cargo_package_version": cli_uses_cargo_version,
        "mcp_uses_cargo_package_version": mcp_uses_cargo_version,
        "capability_uses_cargo_package_version": capability_uses_cargo_version,
        "observed_binary_matches_cargo": observed_binary_matches_cargo,
        "cargo_version_matches_latest_tag": workspace_version == tag_version,
        "binary_expected_version_matches_latest_tag": workspace_version == tag_version,
    }
    version_identity_aligned = (
        version_gates["latest_tag_matches_changelog"]
        and version_gates["cargo_version_matches_latest_tag"]
        and version_gates["binary_expected_version_matches_latest_tag"]
        and observed_binary_matches_cargo
    )

    source_only_consistent = all(source_only_checks.values())
    embedding_runtime_consistent = all(runtime_embedding_checks.values())
    embedding_docs_match_runtime = embedding_runtime_consistent and all(
        embedding_doc_checks.values()
    )
    format_check = inspect_format(repo, check_fmt)

    blockers: list[str] = []
    if not version_identity_aligned:
        blockers.append("version_identity_drift")
    if not source_only_consistent:
        blockers.append("distribution_policy_drift")
    if not embedding_docs_match_runtime:
        blockers.append("embedding_documentation_drift")
    if format_check["checked"] and not format_check["passed"]:
        blockers.append("workspace_format_drift")

    if not version_identity_aligned:
        status = "NO_GO_VERSION_IDENTITY_DRIFT"
    elif not source_only_consistent:
        status = "NO_GO_DISTRIBUTION_POLICY_DRIFT"
    elif not embedding_docs_match_runtime:
        status = "NO_GO_EMBEDDING_DOCUMENTATION_DRIFT"
    elif format_check["checked"] and not format_check["passed"]:
        status = "NO_GO_WORKSPACE_FORMAT_DRIFT"
    else:
        status = "READY_FOR_OWNER_RELEASE_DECISION"

    return {
        "schema": SCHEMA,
        "run_type": "read_only_release_truth_gate",
        "repository": str(repo),
        "status": status,
        "verdict": "NO_GO" if status.startswith("NO_GO_") else "OWNER_GATED",
        "publication_allowed_now": False,
        "owner_gate_required": True,
        "creates_tag": False,
        "publishes_release": False,
        "writes_repository": False,
        "reads_credential_content": False,
        "source_identity": {
            "head": head,
            "latest_tag": tag,
            "latest_tag_version": tag_version,
            "latest_tag_commit": tag_commit,
            "latest_tag_date": tag_date,
            "commits_since_latest_tag": commits_since_tag,
            "changelog_latest_release": changelog_latest,
            "changelog_has_unreleased_section": "## [Unreleased]" in changelog,
        },
        "cargo_identity": {
            "workspace_package_version": workspace_version,
            "workspace_member_version_inheritance": member_inheritance,
            "bridge_package_name": bridge_package.get("name"),
            "bridge_inherits_workspace_version": bridge_inherits_workspace_version,
            "binary_name": "agent-bridge" if binary_declared else None,
            "binary_expected_version": workspace_version,
            "mcp_expected_version": workspace_version,
            "capability_expected_version": workspace_version,
        },
        "binary_observation": binary_observation,
        "version_identity": {
            "aligned": version_identity_aligned,
            "gates": version_gates,
        },
        "distribution_policy": {
            "mode": "source_only" if source_only_consistent else "inconsistent",
            "consistent": source_only_consistent,
            "checks": source_only_checks,
        },
        "embedding_truth": {
            "compiled_default_model": "gte-multilingual-base",
            "compiled_default_dimension": 768,
            "hash_fallback_dimension": 384,
            "optional_onnx_dimension": 384,
            "runtime_consistent": embedding_runtime_consistent,
            "docs_match_runtime": embedding_docs_match_runtime,
            "runtime_checks": runtime_embedding_checks,
            "documentation_checks": embedding_doc_checks,
        },
        "format_check": format_check,
        "blockers": blockers,
        "required_owner_decisions": [
            "Choose one version identity contract for v* source markers and Cargo/binary/MCP surfaces.",
            "Choose the next semantic version only after reviewing the Unreleased change set.",
            "Authorize tag creation/publication only after clean-checkout format, build, and test gates pass.",
        ],
        "next_safe_actions": [
            "Keep exact build provenance anchored to a Git commit until version identity is aligned.",
            "Reduce workspace format drift in scoped, reviewable commits rather than one bulk rewrite.",
            "Re-run this gate with --check-fmt and an explicit --binary before a release decision.",
        ],
    }


def write_output(packet: dict[str, Any], output: str | None) -> None:
    rendered = json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=str(Path(__file__).resolve().parent.parent),
        help="Agent-Bridge repository root.",
    )
    parser.add_argument("--binary", help="Optional built agent-bridge binary to inspect.")
    parser.add_argument(
        "--check-fmt",
        action="store_true",
        help="Run read-only `cargo fmt --all -- --check` and summarize drift.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the gate status is NO_GO_*.",
    )
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args(argv)

    packet = build_gate(Path(args.repo), binary=args.binary, check_fmt=args.check_fmt)
    write_output(packet, args.output)
    if args.strict and packet["status"].startswith("NO_GO_"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
