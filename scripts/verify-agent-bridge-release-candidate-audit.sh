#!/usr/bin/env bash
# Verify the Agent-Bridge release-candidate audit without rerunning build/test.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/agent-bridge-release-candidate-audit.py"
EVIDENCE="$ROOT_DIR/docs/reports/goal-c-u/2026-07-09-agent-bridge-release-candidate-evidence.json"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-09-agent-bridge-release-candidate-audit.md"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-release-candidate-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

output_json="$tmpdir/audit.json"
python3 "$HELPER" \
  --repo "$ROOT_DIR" \
  --check-fmt \
  --execution-evidence "$EVIDENCE" \
  --output "$output_json"

python3 - "$output_json" "$EVIDENCE" <<'PY'
import json
import re
import sys
from pathlib import Path

packet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
evidence = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

assert packet["schema"] == "agent_bridge.release_candidate_audit.v0"
assert packet["run_type"] == "read_only_release_candidate_audit"
assert packet["status"] == "OWNER_GATE_REMOTE_CI"
assert packet["verdict"] == "OWNER_GATED"
assert packet["version_identity_policy"] == "unified"
assert packet["version_change_allowed_now"] is False
assert packet["tag_creation_allowed_now"] is False
assert packet["release_publication_allowed_now"] is False
assert packet["benchmark_continuation"] == "WAIT_VALUE_GATE"
assert packet["writes_repository"] is False
assert packet["release_truth_status"] == "READY_FOR_OWNER_RELEASE_DECISION"
assert packet["version_identity_aligned"] is True

source = packet["source_identity"]
assert re.fullmatch(r"[0-9a-f]{40}", source["head"])
assert source["latest_tag"] == "v0.14.0"
assert source["latest_tag_version"] == "0.14.0"
assert source["changelog_latest_release"] == "0.14.0"
assert source["commits_since_latest_tag"] >= 80

commits = packet["commit_profile"]
assert commits["commit_count"] >= 80
assert commits["type_counts"]["feat"] >= 35
assert commits["type_counts"]["fix"] >= 7
assert commits["type_counts"]["style"] >= 7
assert commits["type_counts"]["test"] >= 10
assert commits["explicit_breaking_change_count"] == 0
assert commits["explicit_breaking_changes"] == []

changes = packet["change_profile"]
assert changes["changed_file_count"] >= 176
assert changes["additions"] >= 114600
assert changes["deletions"] >= 81092
assert changes["binary_file_count"] == 0
assert changes["path_group_counts"]["crates/bridge"] >= 63

assert all(packet["public_surface_signals"].values())
semver = packet["semver_recommendation"]
assert semver == {
    "released_baseline": "0.14.0",
    "recommended_candidate": "0.15.0",
    "reason": "feature_additions_require_minor",
    "recommendation_only": True,
    "version_file_modified": False,
}

fmt = packet["format_gate"]
assert fmt["checked"] is True
assert fmt["passed"] is True
assert fmt["diff_file_count"] == 0
assert fmt["partitions"] == {}
assert packet["format_repair_order"] == [
    "examples_and_tests",
    "store_runtime",
    "bridge_runtime_other",
    "bridge_mcp_main",
]

execution = packet["execution_evidence"]
assert execution["provided"] is True
assert execution["applicable"] is True
assert execution["source_is_ancestor"] is True
assert execution["source_commit"] == "d717a53437d6fb50a474b433e6ec7d5a25289c57"
assert execution["runtime_changes_since_source"] == []
assert execution["matrix_passed"] is True
assert execution["remote_matrix_complete"] is False

assert evidence["schema"] == "agent_bridge.release_candidate_execution_evidence.v0"
assert evidence["source_worktree"] == {
    "mode": "isolated_branch_worktree",
    "clean_before": True,
    "clean_after": True,
    "removed_after_run": False,
}
assert evidence["artifact_cache"]["mode"] == "warm_shared_target"
assert evidence["artifact_cache"]["cold_cache_claim"] is False
assert evidence["platform"]["jobs"] == 1
assert evidence["binary_observation"] == (
    "agent-bridge 0.14.0 (v0.14.0-80-gd717a534; d717a53437d6)"
)

results = evidence["results"]
assert results["fmt"]["status"] == 0
assert results["fmt"]["diff_file_count"] == 0
assert results["fmt"]["log_bytes"] == 0
assert results["fmt"]["log_sha256"] == (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)
assert results["build"]["status"] == 0
assert results["test"]["status"] == 0
assert results["test"]["passed"] == 2507
assert results["test"]["failed"] == 0
assert results["clippy"]["status"] == 0
assert results["clippy"]["advisory"] is True
assert results["no_default_build"]["status"] == 0
assert results["no_default_test"]["status"] == 0
assert results["no_default_test"]["passed"] == 1477
assert results["no_default_test"]["failed"] == 0
for result in results.values():
    assert re.fullmatch(r"[0-9a-f]{64}", result["log_sha256"])

assert evidence["remote_ci"]["status"] == "not_observed_owner_auth_gate"
assert evidence["writes_version"] is False
assert evidence["creates_tag"] is False
assert evidence["publishes_release"] is False
assert evidence["runs_benchmark"] is False
assert packet["blockers"] == ["remote_linux_macos_ci_unverified"]

print("Agent-Bridge release-candidate JSON verification passed")
PY

if ! python3 "$HELPER" \
  --repo "$ROOT_DIR" \
  --check-fmt \
  --execution-evidence "$EVIDENCE" \
  --strict > "$tmpdir/strict.out"; then
  echo "expected strict candidate audit to accept owner-gated non-NO-GO status" >&2
  exit 1
fi

python3 - "$ROOT_DIR/README.md" "$ROOT_DIR/CHANGELOG.md" "$REPORT" <<'PY'
import sys
from pathlib import Path

readme = Path(sys.argv[1]).read_text(encoding="utf-8")
changelog = Path(sys.argv[2]).read_text(encoding="utf-8")
report = Path(sys.argv[3]).read_text(encoding="utf-8")

assert "scripts/agent-bridge-release-candidate-audit.py" in readme
assert "recommends a candidate version but never writes one or creates a tag" in readme
assert "Release-candidate audit is reproducible without publishing" in changelog
assert "NO_GO_FORMAT_DRIFT" in changelog
assert "OWNER_GATE_REMOTE_CI" in changelog

required = [
    "# Agent-Bridge Release Candidate Audit",
    "Source base commit: `d717a534`",
    "Run type: owner-authorized candidate audit, no version or tag write",
    "candidate_status: OWNER_GATE_REMOTE_CI",
    "version_identity_policy: unified",
    "version_change_allowed_now: false",
    "tag_creation_allowed_now: false",
    "benchmark_continuation: WAIT_VALUE_GATE",
    "agent_bridge_release_candidate_audit_20260709",
    "codex-agent-bridge-release-candidate-audit-20260709_active",
    "Forum thread: `design#119`, post `3014`",
    "agent_bridge_unified_version_identity_policy_20260709",
    "schema: agent_bridge.release_candidate_audit.v0",
    "released_baseline: 0.14.0",
    "recommended_candidate: 0.15.0",
    "recommendation_only: true",
    "commit_count: 80",
    "feat: 35",
    "explicit_breaking_change_count: 0",
    "changed_file_count: 176",
    "schema_v40_present: true",
    "schema_v41_present: true",
    "format_diff_file_count: 0",
    "original_format_diff_file_count: 43",
    "6f3ec818",
    "5175c83b",
    "workspace_build_status: PASS",
    "workspace_test_status: PASS",
    "workspace_tests_passed: 2507",
    "workspace_tests_failed: 0",
    "hash_only_build_status: PASS",
    "hash_only_tests_passed: 1477",
    "clippy_status: PASS_ADVISORY",
    "remote_ci_status: UNVERIFIED_OWNER_AUTH_GATE",
    "no Cargo version edit",
    "no tag creation or release publication",
    "no benchmark execution",
]
missing = [needle for needle in required if needle not in report]
if missing:
    raise SystemExit("Missing release-candidate report anchors: " + ", ".join(missing))

for forbidden in [
    "version_change_allowed_now: true",
    "tag_creation_allowed_now: true",
    "release_publication_allowed_now: true",
    "candidate_status: READY",
    "candidate_status: NO_GO",
    "benchmark_continuation: active",
]:
    assert forbidden not in report

semver_index = report.index("## Semver Assessment")
format_index = report.index("## Format Partition")
matrix_index = report.index("## Clean Worktree Matrix")
remote_index = report.index("## Remote CI Boundary")
boundary_index = report.index("## Boundary")
assert semver_index < format_index < matrix_index < remote_index < boundary_index

print("Agent-Bridge release-candidate report verification passed")
PY
