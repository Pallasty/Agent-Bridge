# Goal C U Standing Report Refresh - 2026-06-23

Host: macOS `maxiaodeMac-Pro.local`

Report timestamp: `2026-06-23T11:01:40Z`

Source commit: `a13164d` (`Merge remote-tracking branch 'github/master'`)

Scope: report-first refresh; no runtime implementation

## Verdict

`U` is now a real standing surface, not only a design idea:

- store-side embedding health is available through `agent-bridge
  continuity-report`;
- held-out recall remains owned by `crates/bridge/examples/recall_eval.rs`;
- trigger-recall runtime-shaped and baseline-shadow evidence remain eval-only
  aio2 lanes;
- Palace graph health is observable but still too sparse for PageRank or
  centrality to become a continuity prior.

This refresh does not add an MCP tool, mutate memory, change `memory_search`,
change ranking, reindex vectors, write graph edges, or authorize an executor.

## Source Anchors

| Anchor | Value |
|---|---|
| repo worktree | `/Users/pallasting/Projects/agent-bridge` |
| source commit | `a13164d` |
| source subject | merge of `9a557df` report refresh and `7e6e731` baseline acceptance audit |
| deployed CLI | `agent-bridge continuity-report` |
| active profile | Codex Desktop, `gpt-5.5`, `xhigh`, `essential`, `codex-lean` |
| controlling thread | forum #120 |
| latest board post by this lane | #3961 |

## Board Window

Thread #120 had no new posts after #3961 at the start of this refresh. During
final verification, #3966 added a new paper-grounded embedder-upgrade finding.
That finding does not invalidate this report; it adds a separate candidate input
for the memory-continuity lane.

Current board direction consumed:

- #3961 closes the second hard-family eval slice after another process landed
  the canonical implementation on GitHub.
- The case #8 remote-session family is now replayed on the Mac pinned snapshot.
- The next useful slice is consuming the new report evidence into either a
  production-facing opt-in design review or a smaller Codex telemetry
  failure-mode fix, not another projection family.
- #3966 argues that Chinese hard misses may require a Chinese in-domain
  embedding model candidate test, not only anisotropy/whitening work.

## Runtime And Lifecycle

`mcp_lifecycle_digest(include_runtime_health=true, include_local_install=true)`
reported:

| Axis | Value |
|---|---|
| lifecycle state | `ready` |
| readiness state | `ready` |
| readiness warnings | `0` |
| daemon HTTP | `http://127.0.0.1:7878/healthz` ok |
| Palace health | `http://127.0.0.1:7979/healthz` ok |
| Palace graph | observed |
| Palace semantic events | ok |
| current exposed tools | `40` |
| one-hour scoped failing tools | `0` |

This makes the current report window operationally usable. It is not, by
itself, continuity-lift evidence.

## Event Spine

`event_spine_snapshot(window_secs=86400, limit=200, include_events=false)`
reported:

| Metric | Value |
|---|---:|
| candidate events | 207 |
| included events | 200 |
| truncated events | 7 |
| tool-call rows | 193 |
| tool-error rows | 7 |
| hash chain verified | true |

Chain head:

```text
81df620c5a8a640eb8d368ff288f88b32efdf26823a686e648a675d4762a28ae
```

This is report replayability evidence only.

## Standing Continuity CLI

Command:

```bash
agent-bridge continuity-report
agent-bridge continuity-report --json
```

Current JSON summary:

| Metric | Value |
|---|---:|
| active memories | 3022 |
| embedded active memories | 3022 |
| dominant backend | `multilingual-e5-small` |
| dominant backend vectors | 1629 |
| anisotropy ratio | 0.906 |
| stale vectors | 1393 |
| stale fraction | 0.461 |

Embedding backend mix:

| backend | vectors | share |
|---|---:|---:|
| `multilingual-e5-small` | 1629 | 53.9% |
| `<null pre-v26>` | 1343 | 44.4% |
| `all-MiniLM-L6-v2` | 45 | 1.5% |
| `fnv1a-hash-384` | 5 | 0.2% |

Read:

- e5 anisotropy is still severe. Semantic cosine remains diagnostic, not the
  primary continuity verdict.
- 46.1% stale vectors is hygiene pressure. It should not be framed as a recall
  lever unless a before/after `recall_eval` run moves the held-out anchor.
- The CLI intentionally points recall R@k back to the held-out harness instead
  of recomputing it.

## Held-Out Recall Anchor

Command:

```bash
AB_BASELINE_DB="$HOME/.local/share/agent-bridge/snapshots/state.snapshot.20260623.db" \
  cargo run -p ab-bridge --example recall_eval
```

The pinned run reported:

| Property | Value |
|---|---|
| baseline source | caller-pinned `AB_BASELINE_DB` |
| baseline open mode | read-only pinned snapshot, no migration/WAL init |
| active memories | 3022 |
| graph edges | 5527 |
| selected semantic model | `multilingual-e5-small` |
| semantic status | enabled, real model confirmed |

Per-mode recall over the fixed 18-case corpus:

| mode | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|
| `fts` | 0.278 | 0.556 | 0.667 | 0.366 |
| `hybrid` | 0.278 | 0.500 | 0.667 | 0.364 |
| `semantic` | 0.000 | 0.111 | 0.111 | 0.056 |

Hard-tier runtime anchor:

| mode | hard R@10 |
|---|---:|
| `fts` | 0.375 |
| `fts+graph` | 0.375 |
| `hybrid` | 0.375 |
| `semantic` | 0.125 |

Hard FTS misses remain:

- #1 memory philosophy compression vs more memory;
- #2 tool-surface taxonomy;
- #8 remote long-running agent session steering;
- #9 Agent-Bridge core vision;
- #14 BioCortex shadow-read-only boundary.

This remains the headline continuity anchor. A future runtime retrieval claim
must move this hard-tier row, not only a trigger-specific or family-specific
submetric.

## Case #8 Family Replay

The Mac pinned replay confirms the GitHub implementation from `769f514` through
`53ad6e1`:

| Mode | Expected rank |
|---|---:|
| `remoteproj` | miss |
| `remoteproj_acc` | miss |
| `remoteproj_acc_durable` | 10 |
| `remoteproj_strict` | 10 |
| `role_aware` | 1 |

Controls:

| Control set | Result |
|---|---|
| negative controls | `controls=6 nonempty_accepted=0 false_target_hits=0 work_memory_hits=0` |
| positive controls | `durable_hits=6 strict_hits=6 strict_chain_hits=6 role_aware_hits=6 role_aware_rank1_hits=6` |

Aggregate:

| mode | n | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|---:|
| `strict_projected_families` | 2 | 0.000 | 0.500 | 1.000 | 0.300 |
| `role_aware_hard_families` | 2 | 1.000 | 1.000 | 1.000 | 1.000 |

Read:

- role-aware hard-family assembly is promising for eval and review;
- the denominator is only two implemented families, so it is not a production
  retrieval metric;
- the main hard-tier anchor still shows case #8 as a production miss.

## Trigger Recall State

The latest trigger-recall work is aio2-native and eval-only.

Current relevant reports:

- `docs/reports/goal-c-u/2026-06-23-trigger-recall-runtime-shaped-audit.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-baseline-acceptance-design.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-baseline-acceptance-audit.md`

Runtime-shaped audit result on aio2:

| Metric | Value |
|---|---:|
| baseline R@10 | 0.857 |
| projected-union R@10 | 1.000 |
| runtime-final R@10 | 1.000 |
| supplemental recovered baseline misses | 2 |
| runtime final lost baseline hits | 0 |
| supplemental false hits after gate | 0 |
| baseline false hits retained | 23 |

Baseline acceptance shadow audit result on aio2:

| Metric | Value |
|---|---:|
| baseline-shadow R@10 | 0.857 |
| true hits lost by shadow gate | 0 |
| positive cases held | 0 |
| baseline false hits before shadow gate | 23 |
| baseline false hits after shadow gate | 0 |
| false hits removed by shadow gate | 23 |

Read:

- supplemental projected candidates can be made safer with query-intent gating;
- the new baseline-shadow audit cleanly separates false-hit reduction from
  supplemental recall expansion on the current aio2 corpus;
- this is strong eval evidence, but still not production authorization;
- the next trigger step is a separate production-facing opt-in design review:
  runtime flag/mode, user-visible fallback semantics for held baseline queries,
  and this audit as a regression gate.

## Palace Graph Health

Runtime health observed Palace graph and semantic events.

Current Palace semantic-events graph stats:

| Metric | Value |
|---|---:|
| nodes | 712 |
| edges | 321 |
| orphan nodes | 497 |
| connected ratio | 0.302 |
| explicit edges | 292 |
| coactivation edges | 29 |
| hub nodes | 12 |
| stale nodes | 0 |
| markdown nodes | 212 |
| sqlite nodes | 500 |

Read:

- graph state is observable again, which is useful;
- orphan pressure is still high enough that PageRank/centrality should remain a
  diagnostic or review aid, not a production retrieval prior;
- graph-hygiene work should report orphan reduction or scope-compatible links
  before any centrality-based recall claim.

## Codex Tool Surface

Seven-day `tool_atlas_snapshot(source=codex,codex_host=desktop,profile=essential)`:

| Metric | Value |
|---|---:|
| exposed tools | 40 |
| observed tools | 33 |
| hot tools | 18 |
| cold tools | 10 |
| failing tools | 4 |

Seven-day `mcp_dispatch_audit(source=codex,codex_host=desktop,profile=essential)`:

| Metric | Value |
|---|---:|
| exposed tools | 40 |
| total calls | 1944 |
| total errors | 18 |
| observed tools | 33 |

Notable rows:

| Tool | Signal | Read |
|---|---|---|
| `capabilities` | p95 about 3049 ms | optimize latency or cache compact diagnostics before demotion |
| `changes_digest` | branch-vs-main merge-base errors | fix failure-mode around repos without `main/master` merge-base |
| `memory_save` | invalid `continuity_role=decision` errors | improve client guidance or validation message; do not demote |
| `work_memory` | `get requires key` validation errors | expected input validation; keep surfaced |
| skills tools | cold but core-value | keep exposed while open-source skills intake remains active |

Read:

- the Codex-facing 40-tool surface is still reasonable for this lane;
- current pressure is more about failure-mode polish and latency than broad
  deletion;
- any demotion should wait for more model/profile-specific telemetry.

## Action Candidates

| Candidate | Owner | Anchor | Falsifier | Rollback / Boundary |
|---|---|---|---|---|
| A. Review production-facing opt-in design for baseline acceptance | aio2 trigger-recall lane | `2026-06-23-trigger-recall-baseline-acceptance-audit.md` | user-visible hold semantics are unclear, or held baseline queries would hide legitimate work | design/review only first; no default `memory_search` change |
| B. Keep `continuity-report` plus pinned `recall_eval` as the standing U pair | Goal C U lane | this report plus CLI output | reports stop producing adopted actions or hard-tier R@k remains unchanged after proposed runtime changes | docs/report only; no MCP surface |
| C. Fix Codex telemetry failure modes | Codex integration lane | `changes_digest` and `memory_save` errors in seven-day audit | errors are stale or disappear under exact current model/profile filters | small patches with focused tests; no profile mutation first |
| D. Graph hygiene before centrality prior | memory graph lane | Palace `497/712` orphan nodes and connected ratio `0.302` | safe scope-compatible links are absent or improve no held-out recall anchor | read-only candidate/review first; no PageRank production prior |
| E. Run read-only Chinese in-domain embedder feasibility compare | memory-continuity lane | #3966 and `cjk_embed_compare.rs` | candidate only wins a small CJK pool but fails to move pinned hard-tier `recall_eval` R@10 | compare-only first; no vector schema migration or re-embed |

## Decision

This refresh marks the current Mac Goal C U slice as report-ready:

- the standing `continuity-report` CLI is present and working;
- Mac pinned `recall_eval` replay is read-only and host-correct;
- case #8 role-aware evidence is replayed on the canonical snapshot;
- trigger-recall has a landed aio2 eval-only baseline-shadow audit;
- graph and tool-surface pressure are visible but not authorized as production
  ranking/profile changes.

The recommended next implementation is **not** another Mac-side U report. If
work continues on aio2, review a production-facing opt-in design for baseline
acceptance using the new audit as the regression gate. If work stays on this
Mac and the lane remains recall-focused, first do the read-only Chinese
in-domain embedder feasibility comparison from #3966; only consider vector
schema migration or re-embed after the pinned hard-tier `recall_eval` anchor
moves. If staying on Codex integration instead, take the smaller telemetry
failure-mode fix (`changes_digest` or `memory_save`) before touching retrieval.

## Verification

Commands run for this refresh:

```bash
agent-bridge continuity-report
agent-bridge continuity-report --json
cargo test -p ab-store read_only_open_does_not_create_missing_parent_dir -- --nocapture
cargo test -p ab-bridge --example recall_eval -- --nocapture
AB_BASELINE_DB="$HOME/.local/share/agent-bridge/snapshots/state.snapshot.20260623.db" \
  cargo run -p ab-bridge --example recall_eval
cargo test -p ab-bridge --example continuity_report -- --nocapture
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
git diff --check
```

Results:

| Check | Result |
|---|---|
| continuity CLI | pass |
| continuity JSON | pass |
| read-only store test | pass |
| `recall_eval` example tests | pass, 29 passed |
| pinned recall replay | pass, metrics above |
| `continuity_report` example test target | pass, 0 tests |
| `trigger_recall_eval` example tests | pass, 27 passed |
| whitespace check after report edit | pass |

Expected existing warnings remained:

- `ab-store` mixed-script confusable warning for the beta test name;
- `ab-bridge` warnings for `ToolPolicy` visibility and unused Option-E helpers.
