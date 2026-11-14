# session_curate dry-run explanations

`session_curate` with explicit `dry_run: true` keeps its existing `scope`,
`options` and `candidates` fields and adds an `explanations` object. Extraction,
candidate order, keys, types, tags, deduplication and limits are unchanged.
Normal saves and `session_handoff` do not gain explanation fields.

```json
{
  "explanations": {
    "schema": "agent_bridge.session_curate.explanations.v1",
    "role_attribution": "input_text_headers_only",
    "task_state_assessed": false,
    "items": [
      {
        "key": "the corresponding final candidate key, including its scope suffix",
        "extraction": "implicit",
        "source": {
          "line_number": 2,
          "raw_line": "我先看已完成的验收和现有待办边界，再把下一步压成一个小验证，避免重复做已经收口的修复。",
          "role": "assistant",
          "role_header_line": 1,
          "section_header_line": null,
          "content_clipped": false
        },
        "matched_signals": [
          {"keyword": "避免", "weight": 0.4, "kind_vote": "lesson"},
          {"keyword": "下一步", "weight": 0.45, "kind_vote": "todo"}
        ],
        "score": 0.85,
        "kind_votes": {"lesson": 0.4, "decision": 0.0, "todo": 0.45},
        "threshold": 0.45,
        "score_applied": true,
        "marker": null
      }
    ]
  }
}
```

The example assumes `[ASSISTANT]` on input line 1; float values may contain
ordinary f32 rounding. `items` has one element per selected candidate, in
candidate order. An empty candidate list has an empty `items` list. Explicit
extraction runs first, so source line numbers need not be in ascending order.

Source lines are one-based lines of the exact supplied `conversation_text`,
not original JSONL transcript coordinates. `raw_line` keeps the full line,
including surrounding whitespace but excluding its line ending. For implicit
extraction, it can be longer than the 400-character stored candidate;
`content_clipped` reports that difference. Capture happens when the candidate
is selected, before later clipping/dedup ambiguity could lead to a guessed
source. Suppressed duplicates have no explanation item.

Role attribution follows standalone, case-insensitive `[USER]`, `[ASSISTANT]`,
`[SYSTEM]`, `[DEVELOPER]` and `[TOOL]` headers. With no such preceding header,
`role` and `role_header_line` are null; prose like “我先” does not imply a role.
Headers are caller-supplied text, not verified identities. The Hook retains
such headers, but its existing input clipping and section rewriting still
apply. This field does not recover information absent from the supplied text.

`extraction` is `implicit`, `explicit_marker` or `explicit_section`. Explicit
markers record `marker`; inherited section bullets record
`section_header_line`. Signals, score and votes describe substring matches
on the full source line against the same existing tables. Each matching
table entry contributes once per line, even if the word occurs repeatedly.
For explicit extraction, `score_applied` is false: these diagnostic matches
and the implicit threshold did not select or classify the task. An explicit
task can therefore have a score below the displayed threshold.

Neither a score nor a role label establishes authorization, a current task,
an unmet/fulfilled condition, or completion. Existing false positives remain
visible; this change supports inspection and does not delete or reclassify
them. Explanations are response-only and are not persisted as memory metadata.
Dry-run still records the existing curation telemetry when a store is present,
but does not save candidate memories.

Run the focused module tests and the isolated MCP comparison against a frozen
pre-change binary and the candidate:

```sh
CARGO_TARGET_DIR=/real-disk/target cargo test -p ab-bridge --lib curate::tests -- --test-threads=1
CARGO_TARGET_DIR=/real-disk/target cargo build -p ab-bridge --bin agent-bridge
python3 scripts/check-session-curate-explanations-mcp.py \
  --baseline /absolute/frozen-baseline/agent-bridge.real \
  --candidate /real-disk/target/debug/agent-bridge \
  --output /absolute/new-evidence-directory
```

The comparator uses fresh owner-owned temporary SQLite databases, hash
embeddings, no host credentials and paginated tool discovery. It compares
all prior dry-run fields, normal save receipts, semantic memory readbacks
and pending output. Before comparing pending order, it retains raw write
clocks and fixes only the isolated memories' `updated_at`: the existing
importance/age sort would otherwise observe different per-row ages when a
debug save batch crosses a second boundary. Production ordering is unchanged.
Its fixed corpus contains observed false positives,
concrete task controls, verbatim real user requests and attribution boundary
cases. Some real requests already have baseline omissions or non-todo kinds;
those are preserved and reported, not silently repaired by this change.
These are diagnostic replays, not new natural-recovery samples.
