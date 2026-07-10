# Agent-Bridge Release Candidate Audit

Date: 2026-07-09

Source base commit: `d717a534`

Run type: owner-authorized candidate audit, no version or tag write

```yaml
candidate_status: OWNER_GATE_REMOTE_CI
version_identity_policy: unified
version_change_allowed_now: false
tag_creation_allowed_now: false
release_publication_allowed_now: false
benchmark_continuation: WAIT_VALUE_GATE
```

AB anchors:

- Durable memory key: `agent_bridge_release_candidate_audit_20260709`
- Work-memory key: `codex-agent-bridge-release-candidate-audit-20260709_active`
- Forum thread: `design#119`, post `3014`
- Owner-policy memory key:
  `agent_bridge_unified_version_identity_policy_20260709`
- Parent release memory key: `agent_bridge_release_truth_gate_20260709`

## Verdict

The unified version identity baseline is now coherent at `0.14.0`, and
unreleased builds expose `git describe` plus source SHA. The post-tag change
set warrants a `0.15.0` candidate recommendation, but this audit does not write
that version.

Local Linux release behavior is healthy on a clean isolated branch worktree:

```yaml
workspace_build_status: PASS
workspace_test_status: PASS
workspace_tests_passed: 2507
workspace_tests_failed: 0
hash_only_build_status: PASS
hash_only_tests_passed: 1477
hash_only_tests_failed: 0
clippy_status: PASS_ADVISORY
```

The local candidate is no longer blocked by format, build, test, or hash-only
checks. It remains owner-gated because authenticated Linux/macOS CI was not
observed for the exact candidate source. Remote CI evidence must precede a
version write or tag decision.

Landed audit artifacts:

```text
scripts/agent-bridge-release-candidate-audit.py
scripts/verify-agent-bridge-release-candidate-audit.sh
docs/reports/goal-c-u/2026-07-09-agent-bridge-release-candidate-evidence.json
docs/reports/goal-c-u/2026-07-09-agent-bridge-release-candidate-audit.md
```

## Audit Contract

```yaml
schema: agent_bridge.release_candidate_audit.v0
execution_evidence_schema: agent_bridge.release_candidate_execution_evidence.v0
candidate_status: OWNER_GATE_REMOTE_CI
version_identity_policy: unified
version_change_allowed_now: false
tag_creation_allowed_now: false
release_publication_allowed_now: false
writes_repository: false
benchmark_continuation: WAIT_VALUE_GATE
```

The helper composes the existing release-truth gate, Git history since the
latest source marker, a read-only format check, and a machine-readable execution
packet. Default mode is diagnostic. `--strict` exits non-zero on `NO_GO_*`.

Execution evidence remains applicable to descendant commits only while every
post-evidence path is an audit document/helper. Any runtime or manifest change
invalidates it and requires a new clean-worktree run.

## Semver Assessment

Source base profile from `v0.14.0..d717a534`:

```yaml
released_baseline: 0.14.0
recommended_candidate: 0.15.0
recommendation_only: true
reason: feature_additions_require_minor
version_file_modified: false
commit_count: 80
type_counts:
  feat: 35
  docs: 14
  test: 10
  fix: 7
  style: 7
  other: 4
  refactor: 2
  chore: 1
explicit_breaking_change_count: 0
```

Change volume:

```yaml
changed_file_count: 176
additions: 114637
deletions: 81092
binary_file_count: 0
```

Public-surface signals:

```yaml
unreleased_added_section_present: true
schema_v40_present: true
schema_v41_present: true
mcp_or_cli_surface_changed: true
source_only_distribution_changed: true
```

There is no explicit `BREAKING CHANGE` or conventional-commit `!` marker.
Nevertheless, this is not a patch-shaped release: 35 feature commits add new
MCP/agent behavior, schema v40 and v41, build identity, retrieval learning,
orphan reaping, tool-surface policy, and source-only distribution changes.
Under the project's pre-1.0 SemVer line, the next minor `0.15.0` is the
appropriate recommendation.

This recommendation is evidence, not authorization. `Cargo.toml`, Cargo.lock,
and release tags remain unchanged in this audit.

## Format Partition

Observed clean-source command:

```bash
cargo fmt --all -- --check
```

```yaml
format_check_passed: true
format_diff_file_count: 0
original_format_diff_file_count: 43
```

The repair was completed in the recorded lower-to-higher review order:

1. `examples_and_tests` (17): twelve bridge examples, two bridge integration
   tests, and three store examples.
2. `store_runtime` (2): `crates/store/src/lib.rs` and `sqlite.rs`.
3. `bridge_runtime_other` (17): feature modules outside the MCP/main surface.
4. `bridge_mcp_main` (7): `main.rs`, `mcp_tools.rs`, and five MCP modules/tests.

The high-churn MCP/main partition stayed last so a large import/wrapping diff
did not hide review of the smaller ownership slices. The 17 examples/tests
landed at `6f3ec818`; the remaining 26 files landed in six format-only commits
from `86ac36ca` through `5175c83b`. A separate clean checkout at `6f3ec818`
reproduced all 26 remaining files byte-for-byte with `cargo fmt --all`.

The machine-readable helper emits every path. Aggregate partitions are:

```text
examples_and_tests:
  crates/bridge/examples/* (12 files)
  crates/bridge/tests/autotune_v4_sensitivity_probe.rs
  crates/bridge/tests/biocortex_capability_ledger_consumer.rs
  crates/store/examples/cjk_embed_compare.rs
  crates/store/examples/reindex_to_active_model.rs
  crates/store/examples/search_probe.rs

store_runtime:
  crates/store/src/lib.rs
  crates/store/src/sqlite.rs

bridge_mcp_main:
  crates/bridge/src/main.rs
  crates/bridge/src/mcp_tools.rs
  crates/bridge/src/mcp_tools/audio.rs
  crates/bridge/src/mcp_tools/biocortex_retrieval.rs
  crates/bridge/src/mcp_tools/memory_biocortex.rs
  crates/bridge/src/mcp_tools/mobile.rs
  crates/bridge/src/mcp_tools/tests.rs
```

## Clean Worktree Matrix

Execution source:

```yaml
source_commit: d717a53437d6fb50a474b433e6ec7d5a25289c57
source_mode: isolated_branch_worktree
source_clean_before: true
source_clean_after: true
worktree_removed_at_evidence_write: false
artifact_cache_mode: warm_shared_target
cold_cache_claim: false
platform: linux_x86_64
rustc: 1.96.0
cargo: 1.96.0
jobs: 1
```

The source checkout was clean and isolated. Cargo reused the main repository's
target directory to stay within the 15 GiB RAM / 11 GiB swap host envelope, so
this is explicitly a warm-cache result. Authenticated remote CI is still
required before tagging; a separate cold-cache run would add local evidence but
would not replace that gate.

Accepted commands pin Cargo, rustc, and rustdoc to the same stable toolchain:

```bash
RUSTC="$(rustup which --toolchain stable rustc)" \
RUSTDOC="$(rustup which --toolchain stable rustdoc)" \
CARGO_BUILD_JOBS=1 \
CARGO_INCREMENTAL=0 \
CARGO_TARGET_DIR=/Data/CascadeProjects/agent-bridge/target \
"$(rustup which --toolchain stable cargo)" build --workspace --all-targets -j 1

# Same environment:
cargo test --workspace --no-fail-fast -j 1
cargo clippy --workspace --all-targets -j 1 -- -W clippy::all
cargo build -p ab-bridge --no-default-features --all-targets -j 1
cargo test -p ab-bridge --no-default-features --lib -j 1
```

Results:

| Gate | Status | Duration | Evidence |
| --- | --- | ---: | --- |
| format check | PASS | 3 s | 0 files / 0 output bytes; log SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| workspace all-targets build | PASS | 300 s | 13 warning headers; log SHA-256 `8b1a812abd45242022f24c993395ac4865e61e290a43ad0a41f454fdf893260a` |
| workspace tests | PASS | 66 s | 2,507 passed, 0 failed, 14 ignored across 63 suites; log SHA-256 `00410882c0852c3403c7e0dae56d6f64ef7505bca140a8387b5cab7cc66928bf` |
| clippy all-targets | PASS_ADVISORY | 139 s | exit 0; 415 warning-header lines; log SHA-256 `63a8d773bc1841e6ac55446e7525f22d3f01f9b354db3f61a49c6f2e0a701ed9` |
| hash-only all-targets build | PASS | 250 s | 13 warning headers; log SHA-256 `7b11b550c22ce3b9e9fb651f28c5cbbe6b33a3510cb32d1e963e8b568be4996e` |
| hash-only bridge lib tests | PASS | 6 s | 1,477 passed, 0 failed, 4 ignored; log SHA-256 `d6cdb61f252083cd27489d11fb6d8d4cd7e1b53f283c4dd2abbf9dd599ac2639` |

Built identity:

```text
agent-bridge 0.14.0 (v0.14.0-80-gd717a534; d717a53437d6)
```

No matrix attempt was excluded. The accepted matrix explicitly pins one stable
toolchain and passes.

## Remote CI Boundary

```yaml
remote_ci_status: UNVERIFIED_OWNER_AUTH_GATE
github_linux_verified: false
github_macos_verified: false
gitlab_linux_verified: false
```

Authenticated CI was intentionally not queried because this audit was not
authorized to inspect or use credentials. No remote result is inferred from
local success.

The checked-in CI contract runs workspace all-targets build and workspace tests
on Ubuntu 22.04 and macOS 14; GitLab mirrors the Linux commands. A candidate
commit still needs authenticated results for the exact SHA, especially macOS.

## Decision Matrix

| Gate | Result | Effect |
| --- | --- | --- |
| unified source/package/runtime identity | PASS | current baseline remains 0.14.0 with traceable unreleased SHA |
| semantic-version recommendation | 0.15.0 | recommendation only; no file write |
| Linux default build/test | PASS | local candidate behavior accepted |
| Linux hash-only build/test | PASS | documented lower-footprint path accepted |
| clippy | PASS_ADVISORY | warning debt recorded, not current CI blocker |
| format | PASS, 0 files | local format blocker closed |
| authenticated Linux/macOS CI | UNVERIFIED | remaining owner/pre-tag gate |

## Boundary

This audit performed no product or release mutation:

- no Cargo version edit;
- no tag creation or release publication;
- no benchmark execution; benchmark remains `WAIT_VALUE_GATE`;
- no dependency installation;
- no credential-content read;
- no runtime, schema, retrieval, embedding, daemon, or AB store write;
- no `cargo fmt` write;
- no remote CI or release claim without evidence.

The only repository changes are read-only release helpers/verifiers, evidence
summary, report, and documentation links.

## Verification

```bash
python3 -m py_compile scripts/agent-bridge-release-candidate-audit.py
bash -n scripts/verify-agent-bridge-release-candidate-audit.sh
scripts/verify-agent-bridge-release-candidate-audit.sh
git diff --check
```

The verifier reruns static Git/format analysis, validates execution evidence,
checks evidence applicability across audit-only descendant commits, asserts the
`0.15.0` recommendation and `OWNER_GATE_REMOTE_CI`, and confirms strict mode
accepts the non-NO-GO packet without authorizing a version write. It does not
rerun the multi-minute Rust matrix.

## Next Step

Do not write `0.15.0` yet. Obtain authenticated Linux/macOS CI for the exact
candidate source and rerun this audit before an owner version-write decision.
