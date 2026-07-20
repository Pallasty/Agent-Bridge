#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[2] / "scripts/eval/fixtures/engram_g14_wasi_g2j_r2_recovery_result_v0.json"


def need(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    receipt = json.loads(FIXTURE.read_text())
    need(receipt["gate"] == "G2J_R2_LOCAL_TOOLCHAIN_RECOVERY_EXECUTION", "gate")
    need(receipt["predecessor"]["g2j_fail_closed_post"] == 4891, "old failure retained")
    need(receipt["preconditions"] == {"owner_authorization_post": 4893, "independent_pre_exec_review_post": 4896}, "preconditions")
    binaries = receipt["binaries"]
    need(len(binaries) == 2 and {item["name"] for item in binaries} == {"rustc", "cargo"}, "pair")
    for item in binaries:
        need(item["absolute_path"].startswith("/Users/pallasting/.rustup/toolchains/1.92.0-aarch64-apple-darwin/bin/"), "absolute path")
        need(item["pre_sha256"] == item["post_sha256"], "sha drift")
        need(item["pre_stat"] == item["post_stat"], "stat drift")
        need(item["version"].startswith(item["name"] + " 1.92.0"), "version")
    need(receipt["execution"] == {"selector_bypassed": True, "empty_environment": True, "disposable_directory": True, "directory_cleanup_confirmed": True}, "execution shape")
    expected_forbidden = {
        "rustup_invoked",
        "network_accessed",
        "toolchain_mutated",
        "dependency_resolution",
        "build_or_test",
        "g2g_retry",
        "runtime_or_deploy",
    }
    need(set(receipt["forbidden_actions"]) == expected_forbidden, "forbidden action fields")
    need(all(value is False for value in receipt["forbidden_actions"].values()), "forbidden action")
    need(receipt["verdict"] == "RECOVERY_PROBE_PASS_EVIDENCE_READY_NO_G2G_RETRY_AUTHORITY", "verdict")
    print("PASS G2J/R2 recovery receipt: direct local probe only; no G2G authority")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f"FAIL G2J/R2: {error}", file=sys.stderr)
        raise SystemExit(1)
