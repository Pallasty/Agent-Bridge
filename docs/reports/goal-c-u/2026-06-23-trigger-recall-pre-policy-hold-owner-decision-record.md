# Trigger Recall Pre-Policy Hold Owner Decision Record

Date: 2026-06-23

Schema:
`agent_bridge.memory.trigger_recall.pre_policy_hold.owner_decision_record.v0`

Scope: docs-only owner/reviewer decision record for the production-review
packet at `0bf9662`.

This record does not approve production `enforce_hold`, does not approve default
`memory_search` changes, does not expose Niche tools outside the all profile,
does not write memory or graph state, and does not change indexing, semantic
retrieval, or graph retrieval.

## Decision

`REVIEW-PACKET-ACCEPTED-AS-EVIDENCE / PRODUCTION-ENFORCE-HOLD-NO-GO`

The production-review packet is accepted as a coherent evidence bundle for
future planning:

```text
docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-production-review-packet.md
```

The owner decision stub remains explicitly non-production:

```json
{
  "owner_decision": "accept_review_packet_as_evidence_only",
  "approved_mode": null,
  "approved_implementation_commit": null,
  "approved_runtime_surface": null,
  "production_enforce_hold_authorized": false,
  "default_memory_search_change_authorized": false,
  "non_niche_exposure_authorized": false,
  "expires_at": null,
  "rollback_confirmed": false
}
```

## Evidence Reviewed

Packet commit:

```text
0bf9662 docs(memory): add pre-policy hold production review packet
```

Current follow-up instruction source:

```text
owner chat instruction on 2026-06-23: proceed in order through the remaining tasks
```

Board references:

- `#2522`: repeatable operator smoke command;
- `#2523`: production-review design plan;
- `#2524`: production-review packet.

Key packet evidence accepted for planning:

- installed binary `/home/pallasting/.local/bin/agent-bridge.real`;
- installed sha256
  `fd7800aedef48732dd044a06b52916893cc246cf2b7f784d7d4f35f5e3a40b4a`;
- `doctor --json`: `ok=true`, `fails=0`; non-trigger warning only for
  `instinct_observer` log rotation;
- repeatable smoke passed with target Niche tool present;
- approved held path: `held_by_query_intent`, `store_search_called=false`;
- approved accepted path: `returned_accepted`, `store_search_called=true`;
- missing approval path: `blocked_to_baseline`;
- operator-disabled path: `operator_disabled`;
- all smoke paths: `read_only=true`, `memory_search_mcp_called=false`;
- portable Stage-2 fixture passed with true hits lost `0`, positive held `0`,
  false hits after gate `0`;
- live Aio2 audit passed with true hits lost `0`, positive held `0`, false hits
  after gate `0`.

## Authorized Next Slice

Allowed next:

- write a docs-only production implementation proposal design;
- keep using the repeatable smoke command as a standing evidence gate;
- name exact proposed implementation commit/mode/surface/rollback requirements
  in the proposal;
- keep production `enforce_hold` blocked until a later owner packet explicitly
  authorizes implementation.

Not allowed by this record:

- implementing production `enforce_hold`;
- enabling production `enforce_hold`;
- changing default `memory_search` behavior, schema, or ordering;
- promoting Niche surfaces into compact/essential profiles;
- adding hidden default-search parameters;
- writing memory or graph state;
- recording coactivation for withheld hits;
- reindexing;
- changing tokenizer, semantic retrieval, or graph retrieval.

## Required Proposal Shape

Any future implementation proposal must remain docs-first and include:

- exact current `HEAD` and `origin/master`;
- exact installed binary hash or statement that binary rollout is not part of
  the proposal;
- repeatable smoke output at the proposal head;
- portable Stage-2 fixture output at the proposal head;
- live Aio2 audit output within the freshness window;
- proposed mode name and runtime surface;
- proposed rollback and operator-disable path;
- expected output schema for held queries;
- explicit default `memory_search` invariants;
- falsifiers that block implementation before code changes.

## Freshness Rule

Before any future production implementation proposal is considered, rerun:

```text
/home/pallasting/.local/bin/agent-bridge.real doctor --json
scripts/verify-trigger-recall-pre-policy-hold-runtime-smoke.sh
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --portable-stage2-fixture
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
git diff --check
```

If any command fails or any metric regresses, production remains blocked and the
proposal must be revised before implementation work.
