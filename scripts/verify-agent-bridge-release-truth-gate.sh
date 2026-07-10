#!/usr/bin/env bash
# Verify the read-only Agent-Bridge release truth gate and factual doc repairs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/agent-bridge-release-truth-gate.py"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-09-agent-bridge-release-truth-gate.md"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-release-truth-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

output_json="$tmpdir/gate.json"
binary_args=()
if [ -x "$ROOT_DIR/target/release/agent-bridge" ]; then
  binary_args=(--binary "$ROOT_DIR/target/release/agent-bridge")
fi

python3 "$HELPER" \
  --repo "$ROOT_DIR" \
  "${binary_args[@]}" \
  --check-fmt \
  --output "$output_json"

python3 - "$output_json" <<'PY'
import json
import re
import sys
from pathlib import Path

packet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

assert packet["schema"] == "agent_bridge.release_truth_gate.v0"
assert packet["run_type"] == "read_only_release_truth_gate"
assert packet["status"] == "NO_GO_VERSION_IDENTITY_DRIFT"
assert packet["verdict"] == "NO_GO"
assert packet["publication_allowed_now"] is False
assert packet["owner_gate_required"] is True
assert packet["creates_tag"] is False
assert packet["publishes_release"] is False
assert packet["writes_repository"] is False
assert packet["reads_credential_content"] is False

source = packet["source_identity"]
assert re.fullmatch(r"[0-9a-f]{40}", source["head"])
assert source["latest_tag"] == "v0.14.0"
assert source["latest_tag_version"] == "0.14.0"
assert source["latest_tag_commit"] == "c74bf3360502ffbc1a7c9a471d939617cc028422"
assert source["latest_tag_date"] == "2026-07-02T19:21:17-07:00"
assert source["commits_since_latest_tag"] >= 67
assert source["changelog_latest_release"] == "0.14.0"
assert source["changelog_has_unreleased_section"] is True

cargo = packet["cargo_identity"]
assert cargo["workspace_package_version"] == "0.1.0"
assert cargo["bridge_package_name"] == "ab-bridge"
assert cargo["bridge_inherits_workspace_version"] is True
assert cargo["binary_name"] == "agent-bridge"
assert cargo["binary_expected_version"] == "0.1.0"
assert cargo["mcp_expected_version"] == "0.1.0"
assert cargo["capability_expected_version"] == "0.1.0"
assert len(cargo["workspace_member_version_inheritance"]) == 13
assert all(cargo["workspace_member_version_inheritance"].values())

binary = packet["binary_observation"]
if binary["checked"]:
    assert binary["parsed_version"] == "0.1.0"
    assert binary["version_output"].endswith(" 0.1.0")

version = packet["version_identity"]
assert version["aligned"] is False
assert version["gates"] == {
    "agent_bridge_binary_declared": True,
    "binary_expected_version_matches_latest_tag": False,
    "bridge_inherits_workspace_version": True,
    "capability_uses_cargo_package_version": True,
    "cargo_version_matches_latest_tag": False,
    "cli_uses_cargo_package_version": True,
    "latest_tag_matches_changelog": True,
    "mcp_uses_cargo_package_version": True,
    "observed_binary_matches_cargo": True,
    "workspace_members_inherit_version": True,
}

distribution = packet["distribution_policy"]
assert distribution["mode"] == "source_only"
assert distribution["consistent"] is True
assert all(distribution["checks"].values())

embedding = packet["embedding_truth"]
assert embedding["compiled_default_model"] == "gte-multilingual-base"
assert embedding["compiled_default_dimension"] == 768
assert embedding["hash_fallback_dimension"] == 384
assert embedding["optional_onnx_dimension"] == 384
assert embedding["runtime_consistent"] is True
assert embedding["docs_match_runtime"] is True
assert all(embedding["runtime_checks"].values())
assert all(embedding["documentation_checks"].values())

fmt = packet["format_check"]
assert fmt["checked"] is True
assert isinstance(fmt["captured_output_bytes"], int)
if fmt["passed"] is False:
    assert fmt["diff_file_count"] > 0
    assert "workspace_format_drift" in packet["blockers"]

assert "version_identity_drift" in packet["blockers"]
assert len(packet["required_owner_decisions"]) == 3
assert len(packet["next_safe_actions"]) == 3

print("Agent-Bridge release truth JSON verification passed")
PY

if python3 "$HELPER" --repo "$ROOT_DIR" --strict > "$tmpdir/strict.out"; then
  echo "expected strict release truth gate to reject NO_GO status" >&2
  exit 1
fi

python3 - \
  "$ROOT_DIR/README.md" \
  "$ROOT_DIR/docs/CROSS-MACHINE-SYNC.md" \
  "$ROOT_DIR/crates/store/src/vector.rs" \
  "$ROOT_DIR/crates/bridge/Cargo.toml" \
  "$ROOT_DIR/CHANGELOG.md" <<'PY'
import sys
from pathlib import Path

readme, sync_doc, vector, manifest, changelog = [
    Path(path).read_text(encoding="utf-8") for path in sys.argv[1:]
]

assert "### Version provenance" in readme
assert "scripts/agent-bridge-release-truth-gate.py" in readme
assert "model-aware local embedding" in readme
assert "`gte-multilingual-base` at 768 dimensions" in readme
assert "deterministic 384-dim" in readme
assert "Memories get a **384-dim embedding**" not in readme

assert "dimension matches the active" in sync_doc
assert "`gte-multilingual-base` at 768 dimensions" in sync_doc
assert "Each `memory_save` writes a 384-dim embedding" not in sync_doc

assert "Compute a model-aware f32 embedding" in vector
assert "Compute a 384-dim f32 embedding" not in vector
assert '"gte-multilingual-base" => 768' in vector

assert "Source builds enable `onnx-embed` by default" in manifest
assert "Prebuilt release binaries are built" not in manifest

assert "Release truth is now explicit and machine-checkable" in changelog
assert "NO_GO_VERSION_IDENTITY_DRIFT" in changelog

print("Agent-Bridge release and embedding documentation verification passed")
PY

python3 - "$REPORT" <<'PY'
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
required = [
    "# Agent-Bridge Release Truth Gate",
    "Source base commit: `5f5002a8`",
    "Run type: read-only release identity and documentation gate",
    "release_status: NO_GO_VERSION_IDENTITY_DRIFT",
    "publication_allowed_now: false",
    "owner_gate_required: true",
    "agent_bridge_release_truth_gate_20260709",
    "codex-agent-bridge-release-truth-gate-20260709_active",
    "Forum thread: `design#119`, post `2999`",
    "cascadeprojects_portfolio_audit_20260709",
    "schema: agent_bridge.release_truth_gate.v0",
    "latest_tag: v0.14.0",
    "latest_tag_version: 0.14.0",
    "latest_tag_commit: c74bf3360502ffbc1a7c9a471d939617cc028422",
    "commits_since_latest_tag: 67",
    "changelog_latest_release: 0.14.0",
    "workspace_package_version: 0.1.0",
    "binary_observation: ab-bridge 0.1.0",
    "cargo_version_matches_latest_tag: false",
    "binary_expected_version_matches_latest_tag: false",
    "latest_tag_matches_changelog: true",
    "distribution_mode: source_only",
    "distribution_policy_consistent: true",
    "compiled_default_model: gte-multilingual-base",
    "compiled_default_dimension: 768",
    "hash_fallback_dimension: 384",
    "optional_onnx_dimension: 384",
    "embedding_docs_match_runtime: true",
    "format_check_passed: false",
    "format_diff_file_count: 43",
    "creates_tag: false",
    "publishes_release: false",
    "writes_repository: false",
    "reads_credential_content: false",
    "no Cargo version change",
    "no tag creation or release publication",
    "WAIT_VALUE_GATE",
]

missing = [needle for needle in required if needle not in text]
if missing:
    raise SystemExit("Missing release truth report anchors: " + ", ".join(missing))

for forbidden in [
    "publication_allowed_now: true",
    "owner_gate_required: false",
    "creates_tag: true",
    "publishes_release: true",
    "version_identity_aligned: true",
    "release is ready",
]:
    assert forbidden not in text

evidence_index = text.index("## Version Evidence")
distribution_index = text.index("## Distribution Evidence")
embedding_index = text.index("## Embedding Truth Repair")
format_index = text.index("## Format Gate")
owner_index = text.index("## Owner Gate")
boundary_index = text.index("## Boundary")
assert evidence_index < distribution_index < embedding_index < format_index
assert format_index < owner_index < boundary_index

print("Agent-Bridge release truth report verification passed")
PY
