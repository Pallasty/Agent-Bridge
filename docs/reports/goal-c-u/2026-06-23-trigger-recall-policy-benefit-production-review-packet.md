# Trigger Recall Policy-Benefit Production Review Packet

Date: 2026-06-23

Schema: `agent_bridge.memory.trigger_recall.policy_benefit.production_review_packet.v0`

Scope: board-visible evidence packet for reviewing the current
`policy_benefit_eval.v0` result before any future production `enforce_hold`
implementation proposal.

This packet does not approve production `enforce_hold`, does not implement
production behavior, does not change default `memory_search`, does not register
an MCP tool, and does not write memory, graph edges, indexes, or coactivation
state.

## Verdict

`REVIEW-PACKET-READY-NO-PRODUCTION-GO / OWNER-DECISION-REQUIRED`

The current evidence is coherent enough for owner review of the candidate gate.
It is not sufficient to enable production `enforce_hold`.

Production `enforce_hold` remains `NO-GO` until an owner-approved production
implementation packet names an exact implementation commit, approved mode,
runtime surface, operator switch, and rollback plan.

## Evidence Index

| Item | Value |
|---|---|
| review commit | `7171e7d test(memory): repair live policy benefit gate` |
| branch | `codex/goal-c-policy-benefit-repair-20260623` |
| remote | `github/codex/goal-c-policy-benefit-repair-20260623` |
| parent master | `7c79675 test(memory): add live mac policy benefit eval` |
| repair report | `docs/reports/goal-c-u/2026-06-23-trigger-recall-policy-benefit-repair.md` |
| memory key | `trigger_recall_policy_benefit_repair_20260623_7171e7d` |
| board post | thread `#120`, post `#4046` |
| live DB host | `maxiaodeMac-Pro.local` via Tailscale |
| live DB path | `/Users/pallasting/Library/Application Support/agent-bridge/state.db` |
| Mac validation worktree | `/Users/pallasting/Projects/agent-bridge-trigger-policy-benefit-live-mac` |

## Review Question

Does the repaired `policy_benefit_eval.v0` result justify reopening production
review for trigger-recall pre-policy hold?

Answer: yes, for review only.

Does it authorize production `enforce_hold`?

Answer: no.

## Evidence Reviewed

The previous live Mac run proved the corpus was runnable but not beneficial:

| Metric | Previous Live Result |
|---|---:|
| positive baseline hits | 29/30 |
| baseline false hits before gate | 18 |
| baseline false hits after gate | 18 |
| false hits removed | 0 |
| contract_passed | false |
| ready_for_production_review | false |

The repaired gate separates two concerns:

- explicit exclusion intent is evaluated as a candidate filter for baseline
  false hits;
- `nexus_wuxing_math` remains in the broader 30-case recall eval and CJK
  fallback track, but is excluded from the baseline-findable policy-benefit
  contract because unicode61 projected FTS misses it while scratch CJK fallback
  recovers it.

## Validation Commands

Local Linux worktree:

```bash
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-test-target \
  CARGO_TERM_COLOR=never \
  cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture

CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-test-target \
  CARGO_TERM_COLOR=never \
  cargo run -p ab-bridge --example trigger_recall_eval -- --policy-benefit-fixture
```

Mac live store:

```bash
CARGO_TARGET_DIR=/Users/pallasting/.cache/agent-bridge-test-target \
  CARGO_TERM_COLOR=never \
  cargo test --manifest-path /Users/pallasting/Projects/agent-bridge-trigger-policy-benefit-live-mac/Cargo.toml \
    -p ab-bridge --no-default-features --example trigger_recall_eval -- --nocapture

CARGO_TARGET_DIR=/Users/pallasting/.cache/agent-bridge-test-target \
  CARGO_TERM_COLOR=never \
  cargo run --manifest-path /Users/pallasting/Projects/agent-bridge-trigger-policy-benefit-live-mac/Cargo.toml \
    -p ab-bridge --no-default-features --example trigger_recall_eval -- --check-corpus

CARGO_TARGET_DIR=/Users/pallasting/.cache/agent-bridge-test-target \
  CARGO_TERM_COLOR=never \
  cargo run --manifest-path /Users/pallasting/Projects/agent-bridge-trigger-policy-benefit-live-mac/Cargo.toml \
    -p ab-bridge --no-default-features --example trigger_recall_eval -- --policy-benefit-live-mac
```

Pre-commit:

```bash
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-precommit-target \
  git commit -m "test(memory): repair live policy benefit gate"
```

The first commit attempt failed only because `/Data` was full. Re-running with
`CARGO_TARGET_DIR` on `/home` passed `cargo check -p ab-bridge --all-targets`.

## Current Results

| Check | Result |
|---|---:|
| Linux example tests | 37 passed |
| Mac example tests | 37 passed |
| full live corpus expected refs | 30/30 |
| full live corpus ready | true |
| policy-benefit positive cases | 29 |
| positive baseline hits | 29/29 |
| positive cases held | 0 |
| true hits lost by shadow gate | 0 |
| accepted order drift | 0 |
| baseline false hits before gate | 17 |
| baseline false hits after gate | 0 |
| false hits removed by shadow gate | 17 |
| held controls by reason | explicit_exclusion_candidate_filter=8 |
| contract_passed | true |
| ready_for_production_review | true |
| production_enforce_hold_authorized | false |
| next_required_gate | board_visible_production_review_packet_with_exact_commit |

## Boundary Table

| Boundary | Packet Value | Evidence |
|---|---|---|
| default `memory_search` unchanged | `true` | eval summary |
| production `enforce_hold` authorized | `false` | eval summary + no owner approval |
| MCP tool registration | `false` | code diff only touches example harness |
| memory writes | `false` | eval summary |
| graph writes | `false` | eval summary |
| schema/indexing changes | `false` | eval summary |
| reindex | `false` | eval summary |
| deploy/GTE cutover | `false` | repair report boundary |
| CJK-only case removed from broad eval | `false` | `nexus_wuxing_math` remains in 30-case eval |
| CJK-only case blocks baseline policy-benefit gate | `false` | scoped 29-case live contract |

## Production Blast Radius

The current change is an eval/report change only. It has no runtime blast
radius because it does not touch store retrieval, MCP tool registration, daemon
behavior, or installed `.real`.

A future production implementation would have material blast radius and must be
reviewed separately. At minimum it would need to specify:

- whether hold logic lives in store, MCP wrapper, or a new opt-in runtime path;
- exact operator flag or config;
- exact query-intent reasons that can hold candidates;
- observability fields and redaction behavior;
- rollback command and verification;
- interaction with CJK fallback, GTE cutover, and future reindex work.

## Open Blockers

Production `enforce_hold` remains blocked until all are true:

- owner approves a production implementation packet;
- packet names exact implementation commit and runtime surface;
- packet names exact approved mode and operator switch;
- rollback path is concrete and tested;
- same-head repeatable smoke proves no default `memory_search` regression;
- live Mac corpus remains ready within the freshness window;
- CJK fallback scope is explicitly separated from baseline policy-benefit
  review;
- no default schema, index, graph, semantic, or ranking changes are hidden in
  the implementation.

## Owner Decision Stub

This packet intentionally leaves approval blank:

```json
{
  "owner_decision": "pending",
  "approved_mode": null,
  "approved_implementation_commit": null,
  "approved_runtime_surface": null,
  "production_enforce_hold_authorized": false,
  "default_memory_search_change_authorized": false,
  "expires_at": null,
  "rollback_confirmed": false
}
```

## Next Gate

If the owner accepts this packet, the next implementation slice should still be
an explicit proposal first, not runtime code. The proposal should name the
runtime boundary, feature flag, smoke script, rollback, and exact acceptance
matrix before any production `enforce_hold` behavior is implemented.
