# Correction Co-Surface S2 Readiness Review

Date: 2026-07-01

Status: `READ_ONLY_REVIEW / S2_NOT_RECOMMENDED / FLAG_DISABLED`

## Decision

Keep `AGENT_BRIDGE_CORRECTION_COSURFACE` disabled for long-lived
Agent-Bridge processes.

S1 already passed as a short-lived live-store child-process trial. The current
live state still supports the conservative conclusion from S1: the gated read
path works for targeted cases, but there is not yet enough additional value to
justify an S2 daemon or active-client window by default.

S2 should remain a separate owner-gated runtime experiment. If it is opened
later, it should be a time-boxed window with explicit process ids, start/stop
times, top-k diff capture, rollback, and an after-window environment scan.

## Why Not S2 Now

The current evidence answers the correctness question that motivated the
backfill and S1:

- the A1 write-path rule exists for future canonical correction writes;
- the single historic correction-edge backfill has already been completed;
- copied-DB MCP A/B and live-store short-lived MCP S1 both passed;
- B1 remains default-off unless the explicit env gate is truthy;
- current long-lived processes do not carry the env flag.

Opening S2 would change shared local runtime read behavior for long-lived MCP
clients or daemons. That is a broader operational question than the targeted
correctness evidence requires. The next autonomous slice should therefore keep
working on read-only queue hygiene, report-quality evidence, or offline/copied
DB cases rather than widening live runtime influence.

## Fresh State Checks

Repository baseline after fetching:

```text
master == origin/master == dfa1301 docs(memory): audit thread 106 embedding ram status
working tree clean before this report
```

Doctor:

```text
/home/pallasting/.local/bin/agent-bridge.real doctor
--- 9 ok / 0 warn / 0 fail ---
```

Visible process environment scan:

```text
visible_agent_bridge_real_processes=15
flagged_process_count=0
```

The scan covered `daemon`, `daemon-http`, `palace serve`, `mcp`, and one
short-lived `sync` process visible at scan time. None had
`AGENT_BRIDGE_CORRECTION_COSURFACE` in the process environment.

Live store read-only probe:

```json
{
  "quick_check": "ok",
  "active_memories": 689,
  "active_feedback_corrections": 5,
  "corrects_edges": 5,
  "missing_valid_correction_edges": [],
  "candidate_edge": {
    "from_key": "correction:session_handoff_present_voice_tts_subsystem_20260601:e8f0ab2032038682",
    "to_key": "session_handoff_present_voice_tts_subsystem_20260601",
    "edge_type": "corrects",
    "weight": 1.4,
    "created_at": 1782931382
  }
}
```

The read-only query treats active correction targets as
`status='active'`, `kind='feedback'`, `key LIKE 'correction:%'`, and
`related_keys[0]` or equivalent JSON target entries that point at active memory
rows. No valid active correction target lacked a `corrects` edge.

Targeted tests:

```text
cargo test -p ab-bridge --lib correction_cosurface_default_off_unless_truthy -- --nocapture
test mcp_tools::recall_semantic_fallback_tests::correction_cosurface_default_off_unless_truthy ... ok

cargo test -p ab-bridge --lib b1_cosurface_inserts_corrector_after_corrected_original -- --nocapture
test mcp_tools::tests::b1_cosurface_inserts_corrector_after_corrected_original ... ok
```

Existing warnings observed during the targeted tests:

- mixed-script confusable warning for the existing `coactivation_stats_beta`
  test name that uses Greek beta in source;
- private-interface warning for the existing `ToolPolicy` visibility shape.

No new warning was introduced by this docs-only review.

## Related Evidence

- `2026-07-01-correction-cosurface-link-review.md`
- `2026-07-01-correction-cosurface-live-backfill-preflight.md`
- `2026-07-01-correction-cosurface-single-edge-backfill.md`
- `2026-07-01-correction-cosurface-shadow-diff.md`
- `2026-07-01-correction-cosurface-mcp-ab-smoke.md`
- `2026-07-01-correction-cosurface-ab-enablement-packet.md`
- `2026-07-01-correction-cosurface-s1-closeout.md`
- `2026-07-01-agent-bridge-open-queue-staleness-audit.md`
- `2026-07-01-workflow-feedback-cosurface-latch-usage-evidence.md`

The workflow-feedback usage evidence already captures the reusable lesson: do
not collapse copied-DB proof, short-lived live child-process proof, and
long-lived runtime windows into a single gate.

## S2 Contract If Reopened

If a later owner decision opens S2, use a new packet with all of these fields:

- exact process or client to receive `AGENT_BRIDGE_CORRECTION_COSURFACE=1`;
- start time, planned stop time, and actual stop time;
- process ids and before/after env scans;
- baseline and enabled top-k result keys for the existing query suite;
- negative-control and `exclude_kinds=["feedback"]` checks;
- latency/error notes if visible;
- rollback proof by removing the env override and reconnecting or restarting
  only the affected local process;
- keep-disabled or keep-enabled recommendation after the window.

Do not treat the completed edge backfill, S0.5 copied-DB smoke, or S1
child-process pass as implicit authorization for S2.

## Boundary

This report is read-only documentation. It does not enable
`AGENT_BRIDGE_CORRECTION_COSURFACE`, restart any daemon, deploy binaries, write
memory rows, write graph edges, change ranking policy, change MCP profiles,
change tool routing, or alter default retrieval behavior.
