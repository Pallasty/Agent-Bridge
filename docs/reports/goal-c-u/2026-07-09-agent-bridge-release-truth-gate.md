# Agent-Bridge Release Truth Gate

Date: 2026-07-09

Source base commit: `51c1b2c1`

Run type: read-only release identity and documentation gate

```yaml
release_status: READY_FOR_OWNER_RELEASE_DECISION
format_status: NO_GO_WORKSPACE_FORMAT_DRIFT
publication_allowed_now: false
owner_gate_required: true
runtime_authority: none
creates_tag: false
publishes_release: false
writes_repository: false
reads_credential_content: false
```

AB planning anchors:

- Durable memory key: `agent_bridge_release_truth_gate_20260709`
- Work-memory key: `codex-agent-bridge-release-truth-gate-20260709_active`
- Forum thread: `design#119`, post `2999`
- Portfolio durable memory key: `cascadeprojects_portfolio_audit_20260709`
- Portfolio SSoT: `/Data/CascadeProjects/PORTFOLIO.md` and
  `/Data/CascadeProjects/CURRENT-LANES.md`

## Verdict

The previously observed release-identity mismatch is resolved without creating
a release. Cargo, CLI, MCP initialization, capabilities, the latest source tag,
and the latest CHANGELOG release now share the `0.14.0` baseline. Unreleased
source builds add `git describe` and a short SHA, so they are distinguishable
from the `v0.14.0` tag without inventing `0.15.0`.

```yaml
latest_tag: v0.14.0
changelog_latest_release: 0.14.0
workspace_package_version: 0.14.0
binary_observation: agent-bridge 0.14.0 (git-describe; git-sha)
cargo_version_matches_latest_tag: true
binary_expected_version_matches_latest_tag: true
version_identity_aligned: true
release_status: READY_FOR_OWNER_RELEASE_DECISION
```

`READY_FOR_OWNER_RELEASE_DECISION` is not publication approval. A full gate
with `--check-fmt` still reports `NO_GO_WORKSPACE_FORMAT_DRIFT`, and creating a
new tag or publishing remains an explicit owner action.

## Gate Contract

```yaml
schema: agent_bridge.release_truth_gate.v1
run_type: read_only_release_truth_gate
publication_allowed_now: false
owner_gate_required: true
creates_tag: false
publishes_release: false
writes_repository: false
reads_credential_content: false
```

The standard-library helper reads Git metadata, TOML manifests, current docs,
and an optional binary. `--check-fmt` runs `cargo fmt --all -- --check` and
retains only status, distinct file count, and captured byte count. It never
runs formatting in write mode. `--strict` exits non-zero only for a `NO_GO_*`
result.

## Version Evidence

Observed at the `51c1b2c1` follow-up baseline:

```yaml
latest_tag: v0.14.0
latest_tag_version: 0.14.0
latest_tag_commit: c74bf3360502ffbc1a7c9a471d939617cc028422
latest_tag_date: 2026-07-02T19:21:17-07:00
commits_since_latest_tag: 68
changelog_latest_release: 0.14.0
changelog_has_unreleased_section: true
workspace_package_version: 0.14.0
bridge_package_name: ab-bridge
binary_name: agent-bridge
binary_observation: agent-bridge 0.14.0 (git-describe; git-sha)
mcp_expected_version: 0.14.0
capability_expected_version: 0.14.0
latest_tag_matches_changelog: true
cargo_version_matches_latest_tag: true
binary_expected_version_matches_latest_tag: true
version_identity_aligned: true
```

All 13 default workspace members inherit `workspace.package.version`. The CLI
long version includes package version, `git describe`, and short SHA. MCP
capabilities retain the backward-compatible `version` field and add a `build`
object containing all three fields. A source archive without Git reports
`unknown` honestly; build systems may inject the two source fields explicitly.

## Distribution Evidence

```yaml
distribution_mode: source_only
distribution_policy_consistent: true
readme_source_only: true
changelog_source_only: true
github_release_workflow_absent: true
gitlab_release_pipeline_absent: true
bridge_feature_comment_source_only: true
```

Version tags remain source markers. Aligning the package baseline does not add
a release workflow, binary artifact, or publication path.

## Embedding Truth Repair

```yaml
compiled_default_model: gte-multilingual-base
compiled_default_dimension: 768
hash_fallback_dimension: active_vector_dim
hash_only_build_dimension: 384
optional_onnx_dimension: 384
embedding_runtime_consistent: true
embedding_docs_match_runtime: true
```

The default-feature build selects GTE at 768 dimensions. e5/MiniLM/para-ml
remain 384-dimensional selections. The FNV-1a fallback is allocated with
`vector_dim()`, so it follows the selected model width when ONNX support is
compiled; a `--no-default-features` hash-only build is 384-dimensional.
Operators should use `capabilities.memory.embedding` as runtime truth before a
reindex or store migration.

The sync document is also scoped honestly: `agent-bridge sync` is the current
git/version-vector path for memories, edges, and forum data, while
`scripts/sync-handoff.sh` is a specialized one-way SSH seed/handoff tool.

## Format Gate

Observed read-only command:

```bash
cargo fmt --all -- --check
```

```yaml
format_check_checked: true
format_check_passed: false
format_diff_file_count: 43
```

The formatting debt is independent of version identity. This change does not
apply a bulk rewrite because it would obscure behavioral review across many
unrelated owners. The release helper keeps it as a separate blocker when the
format check is requested.

## Owner Gate

Required decisions:

1. Review the Unreleased change set and choose the next semantic version.
2. Decide whether the remaining format drift must block the next source marker.
3. Authorize tag creation or publication only after the selected clean-checkout
   build and test gates pass.

Exact unreleased provenance is now available from `agent-bridge --version` and
MCP capabilities; pinning a Git commit remains the strongest reproducibility
anchor.

## Portfolio Effect

```yaml
agent_bridge_benchmark_continuation: WAIT_VALUE_GATE
memoryarena_projection_integrity_gate: WAIT_VALUE_GATE
memoryarena_runner_work: WAIT_VALUE_GATE
ama_bench_follow_on: WAIT_VALUE_GATE
```

This release-truth work does not reopen benchmark expansion.

## Boundary

This follow-up made a reversible package-baseline and runtime identity change.
It made:

- Cargo baseline changed from 0.1.0 to 0.14.0;
- no tag creation or release publication;
- no Git history rewrite;
- no release workflow or binary artifact publication;
- no dependency installation;
- no credential-content read or credential rotation;
- no private AB memory export;
- no retrieval ranking, embedding model, schema, or daemon policy change;
- no bulk `cargo fmt` write.

The related `work_memory` fix is orthogonal: terminal saves clear their
short-lived slot, and TTL-expired rows are hidden from all active views. WAIT
and blocked lanes remain visible.

## Verification

```bash
python3 -m py_compile scripts/agent-bridge-release-truth-gate.py
bash -n scripts/verify-agent-bridge-release-truth-gate.sh
scripts/verify-agent-bridge-release-truth-gate.sh
AGENT_BRIDGE_RELEASE_TRUTH_BINARY=target/debug/agent-bridge \
  scripts/verify-agent-bridge-release-truth-gate.sh
cargo test -p ab-bridge --no-default-features work_memory_ --lib -j 1
git diff --check
```

The verifier checks dynamic Git/TOML evidence, source-only distribution,
model-aware embedding truth, optional binary source identity, format summary,
strict-mode behavior, and report boundaries.

## Next Step

Keep release publication owner-gated and reduce format drift in scoped commits.
Keep Agent-Bridge benchmark work at `WAIT_VALUE_GATE` until a benchmark and
product decision are named together.
