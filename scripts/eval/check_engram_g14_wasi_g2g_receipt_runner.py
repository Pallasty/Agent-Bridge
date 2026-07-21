#!/usr/bin/env python3
"""Read-only static checker for the G2G receipt runner."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/eval/engram_g14_wasi_g2g_receipt_runner.py"
WRAPPER = ROOT / "scripts/check-engram-g14-wasi-g2g-receipt-runner.sh"


def need(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wrapper = WRAPPER.read_text(encoding="utf-8")
    need(wrapper == "#!/bin/sh\nexec python3 scripts/eval/check_engram_g14_wasi_g2g_receipt_runner.py\n", "wrapper widened")
    required = (
        "81eaddc51081721cf82db6d44ce571c6f8481187", "/Users/pallasting/Projects",
        'tempfile.mkdtemp(prefix="g2g-receipts.", dir=PROJECTS_ROOT)', "origin/master",
        '"build", "--offline", "--locked", "--manifest-path"', '"--target-dir"',
        'env = os.environ.copy()', 'env["CARGO_NET_OFFLINE"] = "true"',
        '"raw_artifact_sha_scope": "local_observation_only"', '"target_cleanup_attempted"',
        '"target_cleanup_confirmed"', '"target_leftovers"', '"fail_closed_reason"',
        'checked_output(["git", "worktree", "remove", "--force", str(worktree)]', "parent.rmdir()",
        "prepare_lanes(repo, worktrees, targets, receipts)",
        '"git", "worktree", "list", "--porcelain"',
    )
    for token in required:
        need(token in source, f"missing required token: {token}")
    for field in ("absolute_worktree_path", "git_head", "git_tree", "absolute_manifest_path", "absolute_target_path", "expanded_command", "exit_code", "compile_succeeded", "g2e_source_sha256_pre", "g2e_source_sha256_post", "fixture_identity_pre", "fixture_identity_post", "toolchain_identity_pre", "toolchain_identity_post", "raw_artifact_sha256", "negative_evidence", "network_indication", "rustup_selector_reentry", "lockfile_mutation", "dependency_appearance", "output_execution"):
        need(f'"{field}"' in source, f"missing G2K.1 field: {field}")
    need('if "[dependencies]" in text:' in source, "dependency-free manifest check missing")
    need("pre_fixture != FROZEN_FIXTURE" in source and "post_fixture != FROZEN_FIXTURE" in source, "pre/post frozen tuple checks missing")
    need("len(worktrees) != 2" in source and "len(targets) != 2" in source, "two-lane prepare missing")
    need("cleanup_errors = cleanup" in source and "except Exception as error:" in source, "cleanup escape guard missing")
    need('raw_artifact_sha256"] ==' not in source, "raw artifacts compared across lanes")
    need("subprocess.run(argv, cwd=worktree, env=env, text=True, capture_output=True, check=False)" in source, "exact captured build call missing")
    forbidden_text = ("env -i", "CARGO_HOME", 'env["RUSTC"]', 'env["PATH"]', "RUSTFLAGS", 'env["HOME"]', ".unlink(", "os.remove(")
    for token in forbidden_text:
        need(token not in source, f"forbidden behavior present: {token}")
    run_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "subprocess" and n.func.attr in {"run", "call", "Popen", "check_call", "check_output"}]
    need(len(run_calls) == 2, "unexpected subprocess call surface")
    need("artifacts[0]" in source and not any(token in source for token in ("os.exec", "run(artifacts", "Popen(artifacts")), "artifact execution surface")
    print("PASS G2G receipt runner static checker: fixed inputs, bounded paths, exact offline build, receipts and cleanup")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, OSError, SyntaxError) as error:
        print(f"FAIL G2G receipt runner static checker: {error}", file=sys.stderr)
        raise SystemExit(1)
