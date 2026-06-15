# Live Semantic World Runtime - Interaction Feedback Next Revision Plan Acceptance

**2026-06-15 - role: acceptance review / module-test-only**

Parent documents:
- [Interaction feedback protocol](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PROTOCOL_2026_06_15.md)
- [Interaction feedback evidence packet consumption](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_EVIDENCE_PACKET_CONSUMPTION_2026_06_15.md)
- [Interaction feedback consumption report acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_ACCEPTANCE_2026_06_15.md)
- [Interaction feedback next revision plan](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_NEXT_REVISION_PLAN_2026_06_15.md)
- [Interaction feedback semantic patch draft acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_ACCEPTANCE_2026_06_15.md)

Forum anchors:
- `#102` post `#3097`: a separate lane claimed the full
  `scripts/verify-biocortex-retrieval-shadow.sh` integration gate after the MCP
  surface runner. That full-script gate is outside this acceptance.
- `#102` post `#3099`: next-revision plan implementation DONE at `eee98a3`,
  then merged with concurrent GitHub work at `5ddcca5`.

## 0. Purpose

This review decides whether the landed pure next-revision plan can be accepted
as a module/test-only surface.

It does not grant MCP registration, default-profile exposure, live runtime
lookup, store or memory writes, #94 ingestion, Onsen mutation, patch execution,
or verification verdict rewrite.

## 1. Evidence Inspected

Landed feature commit:

```text
eee98a3 feat(lswr): add feedback next revision plan
```

Merged mainline state:

```text
5ddcca5 Merge remote-tracking branch 'github/master'
```

Implemented surface:

```text
agent_bridge.lswr.interaction_feedback_next_revision_plan.v0
```

Code artifacts:

- `crates/bridge/src/lswr_interaction_feedback.rs`
- `crates/bridge/tests/lswr_interaction_feedback_fixture.rs`
- `crates/bridge/examples/lswr_interaction_feedback_next_revision_plan_smoke.rs`

Doc artifacts:

- `LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_NEXT_REVISION_PLAN_2026_06_15.md`

## 2. Verification

Current verification evidence:

```text
cargo fmt -p ab-bridge --check
```

Passed.

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture -- --nocapture
```

Passed: 20 tests.

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_next_revision_plan_smoke -- --format json --assert-ready --assert-read-only
```

Passed. The plan preserves:

- `source_world_verdict=not_verified`;
- `plan_verdict=ready_for_revision`;
- `next_revision.patch_id=patch_arrival_bath_move_002`;
- `next_revision.must_cite=[verify_patch_arrival_bath_move_001, fb_arrival_crowded_001]`;
- `next_revision.allowed_to_apply=false`;
- `next_revision.allowed_to_ingest=false`;
- `writes_state=false`;
- `store_access_required=false`;
- `mcp_tool_registered=false`;
- `implicit_live_runtime_lookup_attempted=false`.

```text
cargo check -p ab-bridge --all-targets
```

Passed with existing warnings only.

```text
bash -n scripts/verify-biocortex-retrieval-shadow.sh
git diff --check HEAD~2..HEAD
```

Passed during the implementation closeout.

This acceptance did not rerun the full `verify-biocortex-retrieval-shadow.sh`
integration gate because #102 post `#3097` separately claimed that full-script
gate. The module/test-only acceptance here relies on the targeted runner and
unit-test evidence above.

## 3. Boundary Review

The next-revision plan is a planner, not an executor.

Accepted behavior:

- derive a plan from an explicit fixture, evidence packet, preflight object, or
  consumption report;
- preserve the source world verdict;
- expose the next revision patch ID from readback;
- require citation of the failed verification and human feedback IDs;
- render a human-auditable Markdown plan;
- block laundered sources while leaving the suspicious source verdict visible.

Rejected behavior:

- apply or mutate a patch;
- call a live LSWR host;
- call store or memory APIs;
- call #94 ingestion;
- register a new MCP tool;
- expose the surface in default or Codex-essential profiles;
- rewrite `not_verified` to `verified`.

## 4. Acceptance Matrix

| Gate | Result | Evidence |
|---|---|---|
| R1: Source report accepted | `PASS` | The plan is ready only when the source report/preflight is accepted. |
| R2: Verdict preserved | `PASS` | `source_world_verdict` and `next_revision.preserved_world_verdict` remain `not_verified` in the happy path. |
| R3: Laundering blocked | `PASS` | Tests block a packet that changes guardrails and changes the world verdict to `verified`; the suspicious verdict remains visible. |
| R4: Revision sources present | `PASS` | The plan exposes both `verify_patch_arrival_bath_move_001` and `fb_arrival_crowded_001` in `next_revision.must_cite`. |
| R5: No action side effects | `PASS` | `allowed_to_apply=false`, `allowed_to_ingest=false`, `writes_state=false`, `store_access_required=false`, `mcp_tool_registered=false`. |
| R6: Human-auditable Markdown | `PASS` | Markdown renders plan verdict, source verdict, failed clause, feedback issue, required citations, and no-action contract. |

## 5. Decision

Decision: `ACCEPTED_MODULE_TEST_ONLY`.

Accepted:

- `agent_bridge.lswr.interaction_feedback_next_revision_plan.v0`;
- `build_interaction_feedback_next_revision_plan(...)`;
- `render_interaction_feedback_next_revision_plan(...)`;
- stdout-only smoke example;
- tests proving ready, direct fixture, and laundered-source blocked paths.

Still not accepted:

- MCP registration;
- default-profile or Codex-essential exposure;
- live runtime lookup;
- file/path input;
- store access;
- memory writes;
- #94 ingestion;
- Onsen mutation;
- patch execution;
- verification verdict rewrite.

## 6. Next Slice

The next safe product slice is to use this plan object as an internal planning
input for drafting the next semantic patch revision.

That follow-up is now accepted as module/test-only in
`LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_ACCEPTANCE_2026_06_15.md`.

If an MCP surface is desired later, it requires a separate all/niche gate review
with the same constraints used for the consumption report MCP wrapper.
