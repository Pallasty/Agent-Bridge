#!/usr/bin/env python3
"""Run the two input-bound, offline G2G compilation receipts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

FIXED_COMMIT = "f63fb2810c054f7f2ce827e2a40e4d36372d7e12"
PROJECTS_ROOT = Path("/Users/pallasting/Projects")
FIXTURE_REL = Path("scripts/eval/fixtures/engram_g14_wasi_g2g_host_build_v0")
MANIFEST_REL = FIXTURE_REL / "Cargo.toml"
LOCK_REL = FIXTURE_REL / "Cargo.lock"
WRAPPER_REL = FIXTURE_REL / "src/lib.rs"
SOURCE_REL = Path("scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/host/src/lib.rs")
RUSTC = Path("/Users/pallasting/.rustup/toolchains/1.92.0-aarch64-apple-darwin/bin/rustc")
CARGO = Path("/Users/pallasting/.rustup/toolchains/1.92.0-aarch64-apple-darwin/bin/cargo")
FROZEN_SOURCE = "52f5f2adeed96e4d70b3ddb03d7793bac6f142b7eb8e125eb591eec4f1207343"
FROZEN_FIXTURE = (
    "187cd13adf218f8bc3bc7f2fb83fe35e658af2b32346b55e1d7cd13746424253",
    "2be6ded55daea7c71b2f5c7be3446d3dc933a164da0c04cd764686bdce8cf89c",
    "9a34d87e2d9795c63e49abea5495e4860c649a0d718cf9f38b26b46749a48f0d",
)
FROZEN_TOOLCHAIN = (
    str(RUSTC), "12cab30aa9890d54445e29149a1e82d18fbe457de12801bd11bbe7e5e7fe33a0",
    "rustc 1.92.0 (ded5c06cf 2025-12-08)", str(CARGO),
    "03e381389f5b7b8e695a744362f3866478f99034b2cf2df6afd4d42cfdab6f67",
    "cargo 1.92.0 (344c4567c 2025-10-21)",
)
NEGATIVE_KEYS = ("network_indication", "rustup_selector_reentry", "lockfile_mutation", "dependency_appearance", "output_execution")


class FailClosed(RuntimeError):
    pass


def sha256(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise FailClosed(f"required regular file missing or symlinked: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_output(argv: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise FailClosed(f"command failed ({result.returncode}): {shlex.join(argv)}: {result.stderr.strip()}")
    return result.stdout.strip()


def exact_child(parent: Path, path: Path, names: set[str]) -> None:
    if not parent.is_absolute() or parent.parent != PROJECTS_ROOT or parent.name.startswith("g2g-receipts.") is False:
        raise FailClosed(f"invalid temporary parent: {parent}")
    if not path.is_absolute() or path.parent != parent or path.name not in names:
        raise FailClosed(f"path escaped exact temporary children: {path}")


def fixture_identity(worktree: Path) -> tuple[str, str, str]:
    manifest = worktree / MANIFEST_REL
    text = manifest.read_text(encoding="utf-8")
    if "[dependencies]" in text:
        raise FailClosed("fixture manifest contains forbidden [dependencies]")
    return (sha256(manifest), sha256(worktree / LOCK_REL), sha256(worktree / WRAPPER_REL))


def fixture_json(value: tuple[str, str, str]) -> dict[str, str]:
    return dict(zip(("manifest_sha256", "lockfile_sha256", "wrapper_sha256"), value, strict=True))


def toolchain_identity() -> tuple[str, str, str, str, str, str]:
    values = (str(RUSTC.resolve(strict=True)), sha256(RUSTC), checked_output([str(RUSTC), "--version"]),
              str(CARGO.resolve(strict=True)), sha256(CARGO), checked_output([str(CARGO), "--version"]))
    return values


def toolchain_json(value: tuple[str, str, str, str, str, str]) -> dict[str, str]:
    keys = ("rustc_absolute_path", "rustc_sha256", "rustc_version", "cargo_absolute_path", "cargo_sha256", "cargo_version")
    return dict(zip(keys, value, strict=True))


def blank_receipt(worktree: Path, target: Path) -> dict[str, Any]:
    return {
        "absolute_worktree_path": str(worktree), "git_head": None, "git_tree": None,
        "absolute_manifest_path": str(worktree / MANIFEST_REL), "absolute_target_path": str(target),
        "expanded_command": None, "exit_code": None, "compile_succeeded": False,
        "g2e_source_sha256_pre": None, "g2e_source_sha256_post": None,
        "fixture_identity_pre": None, "fixture_identity_post": None,
        "toolchain_identity_pre": None, "toolchain_identity_post": None,
        "raw_artifact_sha256": None, "raw_artifact_sha_scope": "local_observation_only",
        "target_cleanup_attempted": False, "target_cleanup_confirmed": False, "target_leftovers": [],
        "negative_evidence": {key: False for key in NEGATIVE_KEYS}, "fail_closed_reason": None,
    }


def detect_markers(output: str) -> dict[str, bool]:
    lower = output.lower()
    return {
        "network_indication": any(x in lower for x in ("updating", "downloading", "http://", "https://", "network")),
        "rustup_selector_reentry": "rustup" in lower,
        "lockfile_mutation": any(x in lower for x in ("lock file", "lockfile", "locking ")),
        "dependency_appearance": any(x in lower for x in ("adding ", "downloading ", "downloaded ")),
        "output_execution": any(x in lower for x in ("running `", "executing ", "     run ")),
    }


def run_lane(repo: Path, worktree: Path, target: Path, receipt: dict[str, Any]) -> None:
    exact_child(worktree.parent, worktree, {"worktree-a", "worktree-b"})
    exact_child(target.parent, target, {"target-a", "target-b"})
    if worktree.exists() or target.exists():
        raise FailClosed("lane worktree or target was not fresh")
    checked_output(["git", "worktree", "add", "--detach", str(worktree), FIXED_COMMIT], cwd=repo)
    receipt["git_head"] = checked_output(["git", "rev-parse", "HEAD"], cwd=worktree)
    receipt["git_tree"] = checked_output(["git", "rev-parse", "HEAD^{tree}"], cwd=worktree)
    if receipt["git_head"] != FIXED_COMMIT or checked_output(["git", "status", "--porcelain"], cwd=worktree):
        raise FailClosed("detached worktree identity or cleanliness mismatch")
    pre_fixture = fixture_identity(worktree)
    pre_source = sha256(worktree / SOURCE_REL)
    pre_toolchain = toolchain_identity()
    receipt.update(g2e_source_sha256_pre=pre_source, fixture_identity_pre=fixture_json(pre_fixture), toolchain_identity_pre=toolchain_json(pre_toolchain))
    if pre_fixture != FROZEN_FIXTURE or pre_source != FROZEN_SOURCE or pre_toolchain != FROZEN_TOOLCHAIN:
        raise FailClosed("pre-build frozen input tuple mismatch")
    if target.exists():
        raise FailClosed("target appeared before build")
    manifest = worktree / MANIFEST_REL
    argv = [str(CARGO), "build", "--offline", "--locked", "--manifest-path", str(manifest), "--target-dir", str(target)]
    receipt["expanded_command"] = "CARGO_NET_OFFLINE=true " + shlex.join(argv)
    env = os.environ.copy()
    env["CARGO_NET_OFFLINE"] = "true"
    result = subprocess.run(argv, cwd=worktree, env=env, text=True, capture_output=True, check=False)
    receipt["exit_code"] = result.returncode
    receipt["negative_evidence"] = detect_markers(result.stdout + "\n" + result.stderr)
    post_fixture = fixture_identity(worktree)
    post_source = sha256(worktree / SOURCE_REL)
    post_toolchain = toolchain_identity()
    receipt.update(g2e_source_sha256_post=post_source, fixture_identity_post=fixture_json(post_fixture), toolchain_identity_post=toolchain_json(post_toolchain))
    if post_fixture != FROZEN_FIXTURE or post_source != FROZEN_SOURCE or post_toolchain != FROZEN_TOOLCHAIN:
        raise FailClosed("post-build frozen input tuple mismatch")
    if checked_output(["git", "rev-parse", "HEAD"], cwd=worktree) != receipt["git_head"] or checked_output(["git", "rev-parse", "HEAD^{tree}"], cwd=worktree) != receipt["git_tree"] or checked_output(["git", "status", "--porcelain"], cwd=worktree):
        raise FailClosed("post-build worktree identity or cleanliness mismatch")
    if any(receipt["negative_evidence"].values()):
        raise FailClosed("forbidden build-output marker observed")
    if result.returncode != 0:
        raise FailClosed("Cargo build returned nonzero")
    artifacts = list((target / "debug/deps").glob("libengram_g14_wasi_g2g_host_build-*.rlib"))
    if len(artifacts) != 1 or not artifacts[0].is_file() or artifacts[0].is_symlink():
        raise FailClosed(f"expected exactly one wrapper rlib, found {len(artifacts)}")
    receipt["raw_artifact_sha256"] = sha256(artifacts[0])
    receipt["compile_succeeded"] = True


def cleanup(repo: Path, parent: Path, worktrees: list[Path], targets: list[Path], receipts: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for target, receipt in zip(targets, receipts, strict=True):
        receipt["target_cleanup_attempted"] = True
        try:
            exact_child(parent, target, {"target-a", "target-b"})
            if target.exists():
                shutil.rmtree(target)
            receipt["target_leftovers"] = list(map(str, target.rglob("*"))) if target.exists() else []
            receipt["target_cleanup_confirmed"] = not target.exists() and receipt["target_leftovers"] == []
            if not receipt["target_cleanup_confirmed"]:
                errors.append(f"target cleanup unconfirmed: {target}")
        except Exception as error:  # cleanup evidence must survive every failure
            receipt["target_leftovers"] = [str(target)] if target.exists() else []
            errors.append(f"target cleanup failed: {target}: {error}")
    for worktree in worktrees:
        try:
            exact_child(parent, worktree, {"worktree-a", "worktree-b"})
            if worktree.exists():
                checked_output(["git", "worktree", "remove", "--force", str(worktree)], cwd=repo)
            if worktree.exists():
                errors.append(f"worktree remained: {worktree}")
        except Exception as error:
            errors.append(f"worktree cleanup failed: {worktree}: {error}")
    try:
        if parent.exists():
            leftovers = list(parent.iterdir())
            if leftovers:
                errors.append("parent not empty: " + ", ".join(map(str, leftovers)))
            else:
                parent.rmdir()
        if parent.exists():
            errors.append(f"parent remained: {parent}")
    except Exception as error:
        errors.append(f"parent cleanup failed: {error}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    repo = args.repo_root.resolve(strict=True)
    parent: Path | None = None
    receipts: list[dict[str, Any]] = []
    failure: str | None = None
    try:
        if checked_output(["git", "rev-parse", "origin/master"], cwd=repo) != FIXED_COMMIT:
            raise FailClosed("origin/master does not match fixed commit")
        parent = Path(tempfile.mkdtemp(prefix="g2g-receipts.", dir=PROJECTS_ROOT)).resolve(strict=True)
        worktrees = [parent / "worktree-a", parent / "worktree-b"]
        targets = [parent / "target-a", parent / "target-b"]
        receipts = [blank_receipt(worktrees[i], targets[i]) for i in range(2)]
        for index in range(2):
            try:
                run_lane(repo, worktrees[index], targets[index], receipts[index])
            except Exception as error:
                receipts[index]["fail_closed_reason"] = str(error)
                raise
    except Exception as error:
        failure = str(error)
    finally:
        if parent is not None:
            cleanup_errors = cleanup(repo, parent, [parent / "worktree-a", parent / "worktree-b"], [parent / "target-a", parent / "target-b"], receipts)
            if cleanup_errors:
                failure = "; ".join(filter(None, (failure, *cleanup_errors)))
        if failure and receipts and not any(r["fail_closed_reason"] for r in receipts):
            receipts[0]["fail_closed_reason"] = failure
    if failure:
        print(json.dumps({"status": "FAIL", "receipts": receipts, "fail_closed_reason": failure}, sort_keys=True))
        return 1
    print(json.dumps({"status": "PASS", "receipts": receipts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
