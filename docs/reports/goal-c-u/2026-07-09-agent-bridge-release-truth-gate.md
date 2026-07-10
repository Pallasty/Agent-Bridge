# Agent-Bridge Release Truth Gate

Date: 2026-07-09

Source base commit: `5f5002a8`

Run type: read-only release identity and documentation gate

```yaml
release_status: NO_GO_VERSION_IDENTITY_DRIFT
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
- Portfolio SSoT:
  - `/Data/CascadeProjects/PORTFOLIO.md`
  - `/Data/CascadeProjects/CURRENT-LANES.md`

## Verdict

Agent-Bridge is not ready for a new version marker or release decision because
its source-release identity and executable/package identity are different:

```yaml
latest_tag: v0.14.0
changelog_latest_release: 0.14.0
workspace_package_version: 0.1.0
binary_observation: ab-bridge 0.1.0
release_status: NO_GO_VERSION_IDENTITY_DRIFT
```

This packet does not choose `0.15.0`, rewrite historical tags, or normalize the
drift by assertion. It makes the mismatch visible and blocks publication until
the owner selects one version identity contract.

The same pass repaired unambiguous documentation drift: the compiled default
embedding is GTE at 768 dimensions, while hash and optional MiniLM/e5/para ONNX
paths are 384 dimensions. Agent-Bridge documentation now describes dimensions
as model-aware instead of fixed at 384.

Landed files:

```text
scripts/agent-bridge-release-truth-gate.py
scripts/verify-agent-bridge-release-truth-gate.sh
docs/reports/goal-c-u/2026-07-09-agent-bridge-release-truth-gate.md
README.md
CHANGELOG.md
docs/CROSS-MACHINE-SYNC.md
crates/store/src/vector.rs
crates/bridge/Cargo.toml
```

## Gate Contract

```yaml
schema: agent_bridge.release_truth_gate.v0
run_type: read_only_release_truth_gate
publication_allowed_now: false
owner_gate_required: true
creates_tag: false
publishes_release: false
writes_repository: false
reads_credential_content: false
```

The standard-library helper reads Git metadata, TOML manifests, release and
embedding documentation, and optionally a built binary. `--check-fmt` runs
`cargo fmt --all -- --check` and retains only status, distinct file count, and
captured byte count. It never runs formatting in write mode.

Default invocation exits zero so operators can inspect a planned `NO_GO`.
`--strict` exits non-zero for any `NO_GO_*` status.

## Version Evidence

Observed at source base `5f5002a8`:

```yaml
head: 5f5002a84bf71c7a293388556adac84fc5a320b5
latest_tag: v0.14.0
latest_tag_version: 0.14.0
latest_tag_commit: c74bf3360502ffbc1a7c9a471d939617cc028422
latest_tag_date: 2026-07-02T19:21:17-07:00
commits_since_latest_tag: 67
changelog_latest_release: 0.14.0
changelog_has_unreleased_section: true
workspace_package_version: 0.1.0
bridge_package_name: ab-bridge
binary_name: agent-bridge
binary_observation: ab-bridge 0.1.0
mcp_expected_version: 0.1.0
capability_expected_version: 0.1.0
```

All 13 default workspace members inherit `workspace.package.version`. The
`agent-bridge` binary is built from package `ab-bridge`; Clap `--version`, MCP
server initialization, and capability reporting all consume
`CARGO_PKG_VERSION`.

Version gates:

```yaml
latest_tag_matches_changelog: true
workspace_members_inherit_version: true
bridge_inherits_workspace_version: true
agent_bridge_binary_declared: true
cli_uses_cargo_package_version: true
mcp_uses_cargo_package_version: true
capability_uses_cargo_package_version: true
observed_binary_matches_cargo: true
cargo_version_matches_latest_tag: false
binary_expected_version_matches_latest_tag: false
version_identity_aligned: false
```

The tag and CHANGELOG therefore form one coherent source-marker identity, and
Cargo/CLI/MCP form another coherent `0.1.0` identity. They are individually
consistent but not aligned with each other.

## Distribution Evidence

The active distribution policy is internally consistent:

```yaml
distribution_mode: source_only
distribution_policy_consistent: true
readme_source_only: true
changelog_source_only: true
github_release_workflow_absent: true
gitlab_release_pipeline_absent: true
bridge_feature_comment_source_only: true
```

`.github/workflows/release.yml` is absent. `.gitlab-ci.yml` explicitly states
that source markers trigger no release pipeline. The stale bridge feature
comment about prebuilt ONNX-free binaries was replaced with the current local
`--no-default-features` build option.

This means the present issue is not an accidental binary publication path. It
is provenance ambiguity for source installs and runtime-reported versions.

## Embedding Truth Repair

Runtime source evidence:

```yaml
compiled_default_model: gte-multilingual-base
compiled_default_dimension: 768
hash_fallback_dimension: 384
optional_onnx_dimension: 384
embedding_runtime_consistent: true
embedding_docs_match_runtime: true
```

`vector_dim_for_model_name` returns 768 for GTE and 384 otherwise. The compiled
ONNX selection defaults to GTE; `all-minilm`, `e5-small`, and `para-ml` remain
explicit 384-dim choices, and the deterministic hash backend remains 384-dim.

Repairs:

- README memory search now says model-aware, with the 768-dim GTE default and
  384-dim alternatives;
- cross-machine sync no longer claims every save is 384-dim;
- `embed_text` API documentation no longer promises a fixed 384-dim vector;
- the bridge feature comment no longer describes removed prebuilt releases;
- README records the difference between source markers and Cargo-reported
  versions and recommends commit-pinned provenance until resolution.

No embedding implementation, store row, reindex path, dimension guard, or
runtime configuration changed.

## Format Gate

Observed read-only command:

```bash
cargo fmt --all -- --check
```

Summary:

```yaml
format_check_checked: true
format_check_passed: false
format_diff_file_count: 43
captured_output_bytes: 3235154
```

The multi-megabyte formatting delta is a separate release blocker. This packet
does not apply it because a bulk rewrite across 43 Rust files would obscure
behavioral review and overlap unrelated ownership. Format repair should be
partitioned into scoped, reviewable commits before a release gate is rerun.

## Owner Gate

Required decisions:

1. Choose one version identity contract for `v*` source markers and
   Cargo/CLI/MCP version surfaces.
2. Review the Unreleased change set and choose the next semantic version; this
   packet intentionally does not infer it.
3. Authorize tag creation or publication only after clean-checkout format,
   build, and test gates pass.

Safe current provenance is the exact Git commit. A source install intended for
reproduction should pin that commit rather than relying on `--version` alone.

## Portfolio Effect

The newer portfolio convergence decision remains authoritative:

```yaml
agent_bridge_benchmark_continuation: WAIT_VALUE_GATE
memoryarena_projection_integrity_gate: WAIT_VALUE_GATE
memoryarena_runner_work: WAIT_VALUE_GATE
ama_bench_follow_on: WAIT_VALUE_GATE
```

This release-truth gate does not reopen benchmark expansion. It addresses the
product/release truth item selected by the shared portfolio SSoT.

## Boundary

This packet made documentation and read-only diagnostic changes only. It made:

- no Cargo version change;
- no tag creation or release publication;
- no Git history rewrite;
- no release workflow or binary artifact creation;
- no dependency installation;
- no credential-content read or credential rotation;
- no private AB memory export;
- no AB store, schema, MCP, retrieval, embedding, daemon, or runtime behavior
  change;
- no bulk `cargo fmt` write.

## Verification

```bash
python3 -m py_compile scripts/agent-bridge-release-truth-gate.py
bash -n scripts/verify-agent-bridge-release-truth-gate.sh
scripts/verify-agent-bridge-release-truth-gate.sh
python3 scripts/agent-bridge-release-truth-gate.py \
  --binary target/release/agent-bridge \
  --check-fmt
git diff --check
```

The verifier asserts dynamic Git/TOML evidence, source-only distribution,
model-aware embedding truth, optional binary parity with Cargo, format summary,
strict-mode rejection, report boundaries, and the expected version-identity
`NO_GO`.

## Next Step

Keep release publication blocked until the owner chooses the version identity
contract. Independently plan a scoped format-drift reduction rather than a
workspace-wide rewrite. Keep Agent-Bridge benchmark work at `WAIT_VALUE_GATE`.
