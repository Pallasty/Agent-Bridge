#!/usr/bin/env python3
"""Build a read-only Agent-Bridge release-candidate audit packet.

The audit consumes the existing release-truth gate, profiles commits since the
latest source marker, optionally partitions cargo-fmt drift, and validates a
machine-readable clean-worktree execution evidence file. It recommends a
semantic version but never edits Cargo metadata, creates a tag, publishes a
release, or reopens benchmark work.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.release_candidate_audit.v0"
EVIDENCE_SCHEMA = "agent_bridge.release_candidate_execution_evidence.v0"
TRUTH_MODULE_NAME = "agent_bridge_release_truth_gate"
COMMIT_TYPE_RE = re.compile(
    r"^(?P<type>[A-Za-z]+)(?:\([^)]*\))?(?P<breaking>!)?:"
)
TEST_RESULT_RE = re.compile(
    r"test result: (?:ok|FAILED)\. (?P<passed>\d+) passed; "
    r"(?P<failed>\d+) failed; (?P<ignored>\d+) ignored; "
    r"(?P<measured>\d+) measured; (?P<filtered>\d+) filtered out"
)


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


def load_truth_module(repo: Path) -> Any:
    path = repo / "scripts" / "agent-bridge-release-truth-gate.py"
    spec = importlib.util.spec_from_file_location(TRUTH_MODULE_NAME, path)
    if spec is None or spec.loader is None:
        fail(f"unable to load release truth gate from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"failed to read JSON {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"JSON root must be an object: {path}")
    return value


def normalize_diff_path(repo: Path, raw: str) -> str:
    path = Path(raw)
    if path.is_absolute():
        try:
            return str(path.resolve().relative_to(repo.resolve()))
        except ValueError:
            return str(path)
    return str(path)


def format_partition(path: str) -> str:
    if path.startswith("crates/bridge/examples/") or path.startswith(
        "crates/bridge/tests/"
    ) or path.startswith("crates/store/examples/"):
        return "examples_and_tests"
    if path == "crates/bridge/src/main.rs" or path == "crates/bridge/src/mcp_tools.rs":
        return "bridge_mcp_main"
    if path.startswith("crates/bridge/src/mcp_tools/"):
        return "bridge_mcp_main"
    if path.startswith("crates/bridge/src/"):
        return "bridge_runtime_other"
    if path.startswith("crates/store/src/"):
        return "store_runtime"
    return "other"


def inspect_format(repo: Path, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {
            "checked": False,
            "passed": None,
            "diff_file_count": None,
            "partitions": {},
            "log_bytes": 0,
            "log_sha256": None,
        }

    completed = run(["cargo", "fmt", "--all", "--", "--check"], cwd=repo, check=False)
    output = completed.stdout + completed.stderr
    paths = sorted(
        {
            normalize_diff_path(repo, match)
            for match in re.findall(r"^Diff in (.+?):\d+:$", output, re.MULTILINE)
        }
    )
    partitions: dict[str, list[str]] = collections.defaultdict(list)
    for path in paths:
        partitions[format_partition(path)].append(path)
    return {
        "checked": True,
        "passed": completed.returncode == 0,
        "diff_file_count": len(paths),
        "partitions": {
            key: {"count": len(values), "files": values}
            for key, values in sorted(partitions.items())
        },
        "log_bytes": len(output.encode("utf-8")),
        "log_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
    }


def conventional_commit_profile(repo: Path, tag: str) -> dict[str, Any]:
    raw = git_text(repo, "log", "--format=%H%x1f%s%x1f%b%x1e", f"{tag}..HEAD")
    type_counts: collections.Counter[str] = collections.Counter()
    breaking_commits: list[dict[str, str]] = []
    commit_count = 0
    for record in raw.split("\x1e"):
        record = record.strip("\r\n")
        if not record:
            continue
        fields = record.split("\x1f", 2)
        if len(fields) == 2:
            fields.append("")
        if len(fields) != 3:
            fail("unexpected git log record shape")
        commit_hash, subject, body = fields
        commit_count += 1
        match = COMMIT_TYPE_RE.match(subject)
        commit_type = match.group("type").lower() if match else "other"
        type_counts[commit_type] += 1
        explicit_breaking = bool(match and match.group("breaking")) or (
            "BREAKING CHANGE" in body.upper()
        )
        if explicit_breaking:
            breaking_commits.append({"commit": commit_hash, "subject": subject})

    return {
        "commit_count": commit_count,
        "type_counts": dict(sorted(type_counts.items())),
        "explicit_breaking_change_count": len(breaking_commits),
        "explicit_breaking_changes": breaking_commits,
    }


def diff_profile(repo: Path, tag: str) -> dict[str, Any]:
    output = git_text(repo, "diff", "--numstat", f"{tag}..HEAD")
    changed_files = additions = deletions = binary_files = 0
    path_groups: collections.Counter[str] = collections.Counter()
    for line in output.splitlines():
        if not line.strip():
            continue
        added, deleted, path = line.split("\t", 2)
        changed_files += 1
        if added == "-" or deleted == "-":
            binary_files += 1
        else:
            additions += int(added)
            deletions += int(deleted)
        parts = path.split("/")
        if parts[0] in {"crates", "docs", "scripts"} and len(parts) > 1:
            group = "/".join(parts[:2])
        else:
            group = parts[0]
        path_groups[group] += 1
    return {
        "changed_file_count": changed_files,
        "additions": additions,
        "deletions": deletions,
        "binary_file_count": binary_files,
        "path_group_counts": dict(path_groups.most_common()),
    }


def next_semver(base: str, commit_profile: dict[str, Any]) -> tuple[str, str]:
    major, minor, patch = [int(part) for part in base.split(".")]
    if commit_profile["explicit_breaking_change_count"]:
        if major == 0:
            return f"0.{minor + 1}.0", "pre_1_0_breaking_change_requires_minor"
        return f"{major + 1}.0.0", "breaking_change_requires_major"
    if commit_profile["type_counts"].get("feat", 0) > 0:
        return f"{major}.{minor + 1}.0", "feature_additions_require_minor"
    if commit_profile["type_counts"].get("fix", 0) > 0:
        return f"{major}.{minor}.{patch + 1}", "fix_only_change_set_requires_patch"
    return base, "no_version_increment_signal"


def evidence_allowed_path(path: str) -> bool:
    return path in {
        "CHANGELOG.md",
        "README.md",
        "scripts/agent-bridge-release-candidate-audit.py",
        "scripts/verify-agent-bridge-release-candidate-audit.sh",
    } or path.startswith(
        "docs/reports/goal-c-u/2026-07-09-agent-bridge-release-candidate-"
    )


def inspect_execution_evidence(
    repo: Path,
    evidence_path: Path | None,
) -> dict[str, Any]:
    if evidence_path is None:
        return {
            "provided": False,
            "applicable": False,
            "source_commit": None,
            "runtime_changes_since_source": [],
            "matrix_passed": False,
            "remote_matrix_complete": False,
            "evidence": None,
        }

    evidence = read_json(evidence_path)
    if evidence.get("schema") != EVIDENCE_SCHEMA:
        fail(f"unexpected execution evidence schema: {evidence.get('schema')!r}")
    source_commit = evidence.get("source_commit")
    if not isinstance(source_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        fail("execution evidence source_commit must be a full Git SHA")

    ancestor = run(
        ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
        cwd=repo,
        check=False,
    ).returncode == 0
    changed_paths = (
        git_text(repo, "diff", "--name-only", f"{source_commit}..HEAD").splitlines()
        if ancestor
        else []
    )
    runtime_changes = sorted(path for path in changed_paths if not evidence_allowed_path(path))

    results = evidence.get("results", {})
    required = ["build", "test", "no_default_build", "no_default_test"]
    matrix_passed = all(results.get(name, {}).get("status") == 0 for name in required)
    remote = evidence.get("remote_ci", {})
    remote_complete = bool(remote.get("github_linux_verified")) and bool(
        remote.get("github_macos_verified")
    )
    applicable = ancestor and not runtime_changes
    return {
        "provided": True,
        "applicable": applicable,
        "source_commit": source_commit,
        "source_is_ancestor": ancestor,
        "changed_paths_since_source": changed_paths,
        "runtime_changes_since_source": runtime_changes,
        "matrix_passed": matrix_passed,
        "remote_matrix_complete": remote_complete,
        "evidence": evidence,
    }


def build_packet(
    repo: Path,
    *,
    check_fmt: bool,
    execution_evidence: Path | None,
) -> dict[str, Any]:
    repo = repo.resolve()
    truth_module = load_truth_module(repo)
    truth = truth_module.build_gate(repo, binary=None, check_fmt=False)
    tag = truth["source_identity"]["latest_tag"]
    released_version = truth["source_identity"]["latest_tag_version"]
    commit_profile = conventional_commit_profile(repo, tag)
    changes = diff_profile(repo, tag)
    recommendation, reason = next_semver(released_version, commit_profile)
    format_result = inspect_format(repo, check_fmt)
    execution = inspect_execution_evidence(repo, execution_evidence)

    changelog = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
    public_surface_signals = {
        "unreleased_added_section_present": "### Added" in unreleased,
        "schema_v40_present": "Schema **v40**" in unreleased,
        "schema_v41_present": "Schema **v41**" in unreleased,
        "mcp_or_cli_surface_changed": any(
            path in changes["path_group_counts"]
            for path in ["crates/bridge", "crates/agent"]
        ),
        "source_only_distribution_changed": "Distribution policy: source only" in unreleased,
    }

    blockers: list[str] = []
    if not truth["version_identity"]["aligned"]:
        blockers.append("version_identity_not_aligned")
    if not execution["provided"] or not execution["applicable"]:
        blockers.append("clean_execution_evidence_missing_or_stale")
    elif not execution["matrix_passed"]:
        blockers.append("linux_build_or_test_matrix_failed")
    if format_result["checked"] and not format_result["passed"]:
        blockers.append("workspace_format_drift")
    if execution["provided"] and not execution["remote_matrix_complete"]:
        blockers.append("remote_linux_macos_ci_unverified")

    if not truth["version_identity"]["aligned"]:
        status = "NO_GO_VERSION_IDENTITY"
    elif not execution["provided"] or not execution["applicable"]:
        status = "NO_GO_EXECUTION_EVIDENCE"
    elif not execution["matrix_passed"]:
        status = "NO_GO_BUILD_OR_TEST"
    elif format_result["checked"] and not format_result["passed"]:
        status = "NO_GO_FORMAT_DRIFT"
    elif not execution["remote_matrix_complete"]:
        status = "OWNER_GATE_REMOTE_CI"
    else:
        status = "READY_FOR_OWNER_VERSION_WRITE_DECISION"

    return {
        "schema": SCHEMA,
        "run_type": "read_only_release_candidate_audit",
        "status": status,
        "verdict": "NO_GO" if status.startswith("NO_GO_") else "OWNER_GATED",
        "version_identity_policy": "unified",
        "version_change_allowed_now": False,
        "tag_creation_allowed_now": False,
        "release_publication_allowed_now": False,
        "benchmark_continuation": "WAIT_VALUE_GATE",
        "writes_repository": False,
        "source_identity": truth["source_identity"],
        "release_truth_status": truth["status"],
        "version_identity_aligned": truth["version_identity"]["aligned"],
        "commit_profile": commit_profile,
        "change_profile": changes,
        "public_surface_signals": public_surface_signals,
        "semver_recommendation": {
            "released_baseline": released_version,
            "recommended_candidate": recommendation,
            "reason": reason,
            "recommendation_only": True,
            "version_file_modified": False,
        },
        "format_gate": format_result,
        "format_repair_order": [
            "examples_and_tests",
            "store_runtime",
            "bridge_runtime_other",
            "bridge_mcp_main",
        ],
        "execution_evidence": execution,
        "blockers": blockers,
        "next_safe_actions": [
            "Land format-only repairs in the recorded low-to-high blast-radius order.",
            "Observe authenticated Linux and macOS CI for the exact candidate commit.",
            "Re-run this audit before asking the owner to write the recommended version.",
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
    parser.add_argument("--check-fmt", action="store_true", help="Run read-only cargo fmt check.")
    parser.add_argument(
        "--execution-evidence",
        help="Optional release-candidate execution evidence JSON.",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on NO_GO status.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args(argv)

    evidence_path = Path(args.execution_evidence).resolve() if args.execution_evidence else None
    packet = build_packet(
        Path(args.repo),
        check_fmt=args.check_fmt,
        execution_evidence=evidence_path,
    )
    write_output(packet, args.output)
    if args.strict and packet["status"].startswith("NO_GO_"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
