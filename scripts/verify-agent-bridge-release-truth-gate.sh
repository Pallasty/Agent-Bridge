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
if [ -n "${AGENT_BRIDGE_RELEASE_TRUTH_BINARY:-}" ]; then
  binary_args=(--binary "$AGENT_BRIDGE_RELEASE_TRUTH_BINARY")
fi

python3 "$HELPER" \
  --repo "$ROOT_DIR" \
  "${binary_args[@]}" \
  --check-fmt \
  --output "$output_json"

python3 - "$output_json" "$HELPER" <<'PY'
import importlib.util
import json
import re
import sys
from pathlib import Path

packet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
spec = importlib.util.spec_from_file_location("release_truth_gate", sys.argv[2])
assert spec is not None and spec.loader is not None
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)

assert packet["schema"] == "agent_bridge.release_truth_gate.v1"
assert packet["run_type"] == "read_only_release_truth_gate"
assert packet["status"] in {
    "NO_GO_WORKSPACE_FORMAT_DRIFT",
    "READY_FOR_OWNER_RELEASE_DECISION",
}
assert packet["verdict"] == (
    "NO_GO" if packet["status"].startswith("NO_GO_") else "OWNER_GATED"
)
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
assert cargo["workspace_package_version"] == "0.14.0"
assert cargo["bridge_package_name"] == "ab-bridge"
assert cargo["bridge_inherits_workspace_version"] is True
assert cargo["binary_name"] == "agent-bridge"
assert cargo["binary_expected_version"] == "0.14.0"
assert cargo["mcp_expected_version"] == "0.14.0"
assert cargo["capability_expected_version"] == "0.14.0"
assert len(cargo["workspace_member_version_inheritance"]) == 14
assert all(cargo["workspace_member_version_inheritance"].values())

binary = packet["binary_observation"]
if binary["checked"]:
    assert binary["parsed_version"] == "0.14.0"
    assert binary["version_output"].startswith("agent-bridge 0.14.0")
    assert binary["git_describe"]
    assert binary["git_sha"]

version = packet["version_identity"]
assert version["aligned"] is True
assert version["gates"] == {
    "agent_bridge_binary_declared": True,
    "binary_expected_version_matches_latest_tag": True,
    "bridge_inherits_workspace_version": True,
    "build_identity_traceable": True,
    "capability_uses_cargo_package_version": True,
    "cargo_version_matches_latest_tag": True,
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
assert embedding["hash_fallback_dimension"] == "active_vector_dim"
assert embedding["hash_only_build_dimension"] == 384
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

assert "version_identity_drift" not in packet["blockers"]
assert len(packet["required_owner_decisions"]) == 3
assert len(packet["next_safe_actions"]) == 3
action_text = " ".join(
    packet["required_owner_decisions"] + packet["next_safe_actions"]
)
if fmt["passed"] is True:
    assert "remaining workspace format drift" not in action_text
    assert "Reduce workspace format drift" not in action_text
    assert "authenticated Linux/macOS CI" in action_text
elif fmt["passed"] is False:
    assert "remaining workspace format drift" in action_text
    assert "Reduce workspace format drift" in action_text
else:
    assert "Run this gate with --check-fmt" in action_text

clean_guidance = " ".join(helper.format_guidance({"checked": True, "passed": True}))
drift_guidance = " ".join(helper.format_guidance({"checked": True, "passed": False}))
unchecked_guidance = " ".join(
    helper.format_guidance({"checked": False, "passed": None})
)
assert "remaining workspace format drift" not in clean_guidance
assert "authenticated Linux/macOS CI" in clean_guidance
assert "remaining workspace format drift" in drift_guidance
assert "Reduce workspace format drift" in drift_guidance
assert "Run this gate with --check-fmt" in unchecked_guidance

print("Agent-Bridge release truth JSON verification passed")
PY

if python3 "$HELPER" --repo "$ROOT_DIR" --check-fmt --strict > "$tmpdir/strict.out"; then
  if grep -q '"status": "NO_GO_' "$output_json"; then
    echo "expected strict release truth gate to reject current NO_GO status" >&2
    exit 1
  fi
elif ! grep -q '"status": "NO_GO_' "$output_json"; then
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
assert "model-aware embedding" in readme
assert "`gte-multilingual-base` at 768 dimensions" in readme
assert "output width follows the active `vector_dim()`" in readme
assert "Memories get a **384-dim embedding**" not in readme

assert "model-aware embedding" in sync_doc
assert "width follows the active model dimension" in sync_doc
assert "Each `memory_save` writes a 384-dim embedding" not in sync_doc

assert "Compute a model-aware f32 embedding" in vector
assert "Compute a 384-dim f32 embedding" not in vector
assert '"gte-multilingual-base" => 768' in vector

assert "Source builds enable `onnx-embed` by default" in manifest
assert "Prebuilt release binaries are built" not in manifest

assert "Release truth is now explicit and machine-checkable" in changelog
assert "latest released baseline (`0.14.0`)" in changelog

print("Agent-Bridge release and embedding documentation verification passed")
PY

python3 - "$REPORT" <<'PY'
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
required = [
    "# Agent-Bridge Release Truth Gate",
    "Source base commit: `51c1b2c1`",
    "Run type: read-only release identity and documentation gate",
    "release_status: READY_FOR_OWNER_RELEASE_DECISION",
    "publication_allowed_now: false",
    "owner_gate_required: true",
    "agent_bridge_release_truth_gate_20260709",
    "codex-agent-bridge-release-truth-gate-20260709_active",
    "Forum thread: `design#119`, post `2999`",
    "cascadeprojects_portfolio_audit_20260709",
    "schema: agent_bridge.release_truth_gate.v1",
    "latest_tag: v0.14.0",
    "latest_tag_version: 0.14.0",
    "latest_tag_commit: c74bf3360502ffbc1a7c9a471d939617cc028422",
    "commits_since_latest_tag: 68",
    "changelog_latest_release: 0.14.0",
    "workspace_package_version: 0.14.0",
    "binary_observation: agent-bridge 0.14.0",
    "cargo_version_matches_latest_tag: true",
    "binary_expected_version_matches_latest_tag: true",
    "version_identity_aligned: true",
    "latest_tag_matches_changelog: true",
    "distribution_mode: source_only",
    "distribution_policy_consistent: true",
    "compiled_default_model: gte-multilingual-base",
    "compiled_default_dimension: 768",
    "hash_fallback_dimension: active_vector_dim",
    "hash_only_build_dimension: 384",
    "optional_onnx_dimension: 384",
    "embedding_docs_match_runtime: true",
    "format_check_passed: false",
    "creates_tag: false",
    "publishes_release: false",
    "writes_repository: false",
    "reads_credential_content: false",
    "Cargo baseline changed from 0.1.0 to 0.14.0",
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
