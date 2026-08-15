#!/usr/bin/env python3
"""Read-only Agent-Bridge source, remote, binary, and worktree truth snapshot."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCHEMA = "agent_bridge.project_truth_snapshot.v0"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
BUILD_SHA_RE = re.compile(r"^[0-9a-f]{12,40}$")


def run(
    args: list[str], *, cwd: Path, timeout: int = 10
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
            close_fds=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return subprocess.CompletedProcess(args, 124, "", "")


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=repo)


def git_text(repo: Path, *args: str) -> str | None:
    completed = git(repo, *args)
    return completed.stdout.strip() if completed.returncode == 0 else None


def status_counts(repo: Path) -> dict[str, Any]:
    completed = git(repo, "status", "--porcelain=v1")
    if completed.returncode != 0:
        return {
            "observed": False,
            "dirty": None,
            "entries": None,
            "staged": None,
            "unstaged": None,
            "untracked": None,
        }
    entries = staged = unstaged = untracked = 0
    for line in completed.stdout.splitlines():
        entries += 1
        if line.startswith("??"):
            untracked += 1
            continue
        if len(line) >= 2 and line[0] != " ":
            staged += 1
        if len(line) >= 2 and line[1] != " ":
            unstaged += 1
    return {
        "observed": True,
        "dirty": staged + unstaged + untracked > 0,
        "entries": entries,
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
    }


def upstream_state(repo: Path, head: str) -> dict[str, Any]:
    upstream = git_text(
        repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
    )
    if upstream is None:
        return {
            "configured": False,
            "ref": None,
            "sha": None,
            "ahead": None,
            "behind": None,
        }
    upstream_sha = git_text(repo, "rev-parse", upstream)
    counts = git_text(
        repo, "rev-list", "--left-right", "--count", f"{head}...{upstream}"
    )
    ahead = behind = None
    if counts:
        fields = counts.split()
        if len(fields) == 2 and all(field.isdigit() for field in fields):
            ahead, behind = map(int, fields)
    return {
        "configured": True,
        "ref": upstream,
        "sha": upstream_sha,
        "ahead": ahead,
        "behind": behind,
    }


def endpoint_identity(url: str) -> dict[str, Any]:
    if "://" in url:
        parsed = urlsplit(url)
        credentialed = bool(
            parsed.password is not None
            or parsed.query
            or parsed.fragment
            or (parsed.username is not None and parsed.scheme not in {"ssh"})
        )
        return {
            "transport": parsed.scheme or "unknown",
            "host": parsed.hostname,
            "path": parsed.path if parsed.scheme == "file" else parsed.path.lstrip("/"),
            "credentialed_url_rejected": credentialed,
        }
    match = re.fullmatch(r"(?:(?P<user>[^@/:]+)@)?(?P<host>[^/:]+):(?P<path>.+)", url)
    if match:
        return {
            "transport": "ssh",
            "host": match.group("host"),
            "path": match.group("path"),
            "credentialed_url_rejected": False,
        }
    path = Path(url).expanduser()
    return {
        "transport": "file",
        "host": None,
        "path": str(path.resolve()),
        "credentialed_url_rejected": False,
    }


def remote_urls(repo: Path, remote: str) -> list[str]:
    urls: list[str] = []
    for args in (
        ("remote", "get-url", "--all", remote),
        ("remote", "get-url", "--push", "--all", remote),
    ):
        value = git_text(repo, *args)
        if value:
            urls.extend(line for line in value.splitlines() if line)
    return list(dict.fromkeys(urls))


def inspect_remote(repo: Path, url: str, branch: str, probe: bool) -> dict[str, Any]:
    identity = endpoint_identity(url)
    result: dict[str, Any] = {
        **identity,
        "branch": branch,
        "probe_status": "NOT_REQUESTED",
        "sha": None,
    }
    if not probe:
        return result
    if identity["credentialed_url_rejected"]:
        result["probe_status"] = "REJECTED_CREDENTIAL_BEARING_URL"
        return result
    completed = run(
        ["git", "ls-remote", url, f"refs/heads/{branch}"], cwd=repo, timeout=15
    )
    if completed.returncode != 0:
        result["probe_status"] = "UNAVAILABLE"
        return result
    fields = completed.stdout.strip().split()
    if len(fields) >= 2 and SHA_RE.fullmatch(fields[0]):
        result["probe_status"] = "OBSERVED"
        result["sha"] = fields[0]
    else:
        result["probe_status"] = "BRANCH_NOT_FOUND"
    return result


def inspect_binary(repo: Path, binary: str | None) -> dict[str, Any]:
    if binary is None:
        return {
            "observed": False,
            "version_observed": False,
            "provenance_observed": False,
            "probe_process_spawned": False,
            "path": None,
            "version": None,
            "git_describe": None,
            "git_sha": None,
        }
    path = Path(binary).expanduser()
    if not path.is_absolute():
        path = repo / path
    if not path.is_file():
        return {
            "observed": False,
            "version_observed": False,
            "provenance_observed": False,
            "probe_process_spawned": False,
            "path": str(path),
            "version": None,
            "git_describe": None,
            "git_sha": None,
        }
    completed = run([str(path), "--version"], cwd=repo)
    if completed.returncode != 0 or completed.stderr.strip():
        return {
            "observed": False,
            "version_observed": False,
            "provenance_observed": False,
            "probe_process_spawned": True,
            "path": str(path),
            "version": None,
            "git_describe": None,
            "git_sha": None,
        }
    output = completed.stdout.strip()
    version_match = re.search(
        r"(?:^|\s)(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)(?=\s|\(|$)", output
    )
    build_match = re.search(r"\(([^;]+);\s*([0-9a-f]{12,40}|unknown)\)$", output)
    version_observed = version_match is not None
    git_sha = (
        build_match.group(2)
        if build_match and BUILD_SHA_RE.fullmatch(build_match.group(2))
        else None
    )
    provenance_observed = build_match is not None and git_sha is not None
    return {
        "observed": version_observed and provenance_observed,
        "version_observed": version_observed,
        "provenance_observed": provenance_observed,
        "probe_process_spawned": True,
        "path": str(path),
        "version": version_match.group(1) if version_match else None,
        "git_describe": build_match.group(1) if build_match else None,
        "git_sha": git_sha,
    }


def worktree_status_totals(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "dirty": sum(row["status"].get("dirty") is True for row in rows),
        "clean": sum(row["status"].get("dirty") is False for row in rows),
        "unobserved": sum(row["status"].get("observed") is not True for row in rows),
    }


def parse_worktrees(repo: Path) -> list[dict[str, Any]]:
    output = git_text(repo, "worktree", "list", "--porcelain")
    if output is None:
        return []
    rows: list[dict[str, Any]] = []
    for block in output.split("\n\n"):
        fields: dict[str, str | bool] = {}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            fields[key] = value if value else True
        path_value = fields.get("worktree")
        if not isinstance(path_value, str):
            continue
        path = Path(path_value)
        branch_value = fields.get("branch")
        rows.append(
            {
                "path": str(path),
                "head": fields.get("HEAD"),
                "branch": (
                    branch_value.removeprefix("refs/heads/")
                    if isinstance(branch_value, str)
                    else None
                ),
                "detached": "detached" in fields,
                "status": status_counts(path),
            }
        )
    return rows


def build_snapshot(
    repo: Path,
    *,
    remote: str,
    remote_branch: str,
    probe_remotes: bool,
    binary: str | None,
    inspect_worktrees: bool,
    include_clean_worktrees: bool = False,
) -> dict[str, Any]:
    root_text = git_text(repo, "rev-parse", "--show-toplevel")
    if root_text is None:
        raise ValueError("not a Git repository")
    root = Path(root_text).resolve()
    head = git_text(root, "rev-parse", "HEAD")
    branch = git_text(root, "branch", "--show-current")
    if head is None:
        raise ValueError("unable to resolve HEAD")
    endpoints = [
        inspect_remote(root, url, remote_branch, probe_remotes)
        for url in remote_urls(root, remote)
    ]
    observed_remote_shas = {
        row["sha"] for row in endpoints if row["probe_status"] == "OBSERVED"
    }
    remote_consensus = (
        len(observed_remote_shas) == 1
        and len(endpoints) > 0
        and all(row["probe_status"] == "OBSERVED" for row in endpoints)
    )
    remote_sha = next(iter(observed_remote_shas)) if remote_consensus else None
    source_status = status_counts(root)
    source = {
        "root": str(root),
        "head": head,
        "branch": branch or None,
        "working_tree": source_status,
        "upstream": upstream_state(root, head),
    }
    installed = inspect_binary(root, binary)
    worktrees = parse_worktrees(root) if inspect_worktrees else []
    worktree_totals = worktree_status_totals(worktrees)
    observations_complete = bool(
        probe_remotes
        and endpoints
        and remote_consensus
        and installed["observed"]
        and source_status["observed"]
        and (not inspect_worktrees or worktree_totals["unobserved"] == 0)
    )
    aligned = bool(
        observations_complete
        and source["working_tree"]["dirty"] is False
        and head == remote_sha
        and installed["git_sha"] is not None
        and remote_sha.startswith(installed["git_sha"])
    )
    verdict = (
        "READY_ALIGNED"
        if aligned
        else (
            "HOLD_INCOMPLETE_OBSERVATION"
            if not observations_complete
            else "HOLD_SOURCE_RUNTIME_REMOTE_DIVERGENCE"
        )
    )
    mismatches: list[str] = []
    if source_status["observed"] is not True:
        mismatches.append("SOURCE_WORKTREE_STATUS_UNOBSERVED")
    if source["working_tree"]["dirty"] is True:
        mismatches.append("SOURCE_WORKTREE_DIRTY")
    if not remote_consensus:
        mismatches.append("REMOTE_CONSENSUS_UNPROVEN")
    if remote_sha is not None and head != remote_sha:
        mismatches.append("SOURCE_HEAD_DIFFERS_FROM_REMOTE")
    if not installed["observed"]:
        mismatches.append("INSTALLED_BINARY_UNOBSERVED")
    elif remote_sha is not None and (
        installed["git_sha"] is None or not remote_sha.startswith(installed["git_sha"])
    ):
        mismatches.append("INSTALLED_BINARY_DIFFERS_FROM_REMOTE")
    if inspect_worktrees and worktree_totals["unobserved"]:
        mismatches.append("WORKTREE_STATUS_UNOBSERVED")
    if not observations_complete:
        next_action = "complete missing source, remote, installed-binary, and worktree observations"
    elif mismatches:
        next_action = (
            "preserve dirty WIP; reconcile from a clean remote-tracking worktree "
            "before build or deploy"
        )
    else:
        next_action = "run fresh-process health and MCP smoke before claiming deployment acceptance"
    visible_worktrees = (
        worktrees
        if include_clean_worktrees
        else [row for row in worktrees if row["status"].get("dirty") is not False]
    )
    return {
        "schema": SCHEMA,
        "verdict": verdict,
        "ready": aligned,
        "source": source,
        "remotes": {
            "name": remote,
            "branch": remote_branch,
            "consensus": remote_consensus,
            "consensus_sha": remote_sha,
            "endpoints": endpoints,
        },
        "installed_binary": installed,
        "summary": {
            "source_head": head,
            "remote_head": remote_sha,
            "installed_binary_sha": installed["git_sha"],
            "source_dirty_entries": source["working_tree"]["entries"],
            "worktree_total": len(worktrees) if inspect_worktrees else None,
            "worktree_dirty": worktree_totals["dirty"] if inspect_worktrees else None,
            "worktree_clean": worktree_totals["clean"] if inspect_worktrees else None,
            "worktree_unobserved": (
                worktree_totals["unobserved"] if inspect_worktrees else None
            ),
            "mismatches": mismatches,
            "next_action": next_action,
        },
        "worktrees": {
            "inspected": inspect_worktrees,
            "total": len(worktrees) if inspect_worktrees else None,
            "dirty": worktree_totals["dirty"] if inspect_worktrees else None,
            "clean": worktree_totals["clean"] if inspect_worktrees else None,
            "unobserved": worktree_totals["unobserved"] if inspect_worktrees else None,
            "rows_are_dirty_or_unobserved_only": inspect_worktrees
            and not include_clean_worktrees,
            "rows": visible_worktrees,
        },
        "nonclaims": [
            "installed binary provenance does not prove the currently connected MCP process identity",
            "the explicitly selected binary is executed with --version; its own side effects are unproven",
            "remote observation does not fetch or mutate local refs",
            "dirty worktrees are inventory only and are never cleaned or removed",
            "READY_ALIGNED is not deployment or live functional acceptance",
        ],
        "observed_effects": {
            "tool_requested_repository_write": False,
            "tool_requested_git_ref_write": False,
            "tool_requested_worktree_write": False,
            "external_binary_probe_spawned": installed["probe_process_spawned"],
            "external_binary_probe_side_effects": (
                "unproven" if installed["probe_process_spawned"] else "not_invoked"
            ),
            "network_read": probe_remotes,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--remote-branch", default="master")
    parser.add_argument("--probe-remotes", action="store_true")
    parser.add_argument("--binary")
    parser.add_argument("--inspect-worktrees", action="store_true")
    parser.add_argument("--include-clean-worktrees", action="store_true")
    args = parser.parse_args()
    try:
        packet = build_snapshot(
            Path(args.repo),
            remote=args.remote,
            remote_branch=args.remote_branch,
            probe_remotes=args.probe_remotes,
            binary=args.binary,
            inspect_worktrees=args.inspect_worktrees,
            include_clean_worktrees=args.include_clean_worktrees,
        )
    except ValueError:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "verdict": "HOLD_NOT_A_GIT_REPOSITORY",
                    "ready": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(packet, sort_keys=True, separators=(",", ":")))
    return 0 if packet["ready"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
