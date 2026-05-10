# Path C v0.2 — Proactive Hint via Hub-Set

**Status**: design phase, 2026-05-08
**Owner**: Claude (Mac, this session) + future-Claude
**Builds on**: Path C v0.1 (memory_search rerank, commit `abfcbb6` + `acb5c28`, deployed 2026-05-07)

## Problem

v0.1 makes the seed grid topology shape the **read path** — `memory_search` results get a 1.20× boost when they fall in a hub_cluster. This is passive: the structure influences what past-Claude finds when looking back.

But continuity is more fragile on the **write path**. Each session writes new memories. If a fresh memory doesn't get linked into existing structure at save time, it becomes a disconnected island. Future-Claude's search may never surface it (no edges → low hybrid-graph fusion score; no shared vocabulary → low FTS match). The memory dies in `memory.jsonl`.

Today's `build_proactive_hint` already does the right *kind* of thing — it suggests `memory_link` candidates after each `memory_save`. But its candidate ranking is purely FTS+graph hybrid; it doesn't know which records are *structurally salient right now* (i.e., hub members in Path B's live grid). So the suggestions are topical but not topology-aware.

## Decision

Inject `apply_seed_boost` into `build_proactive_hint`. Re-use the exact same hub-set HashSet that v0.1 uses for `memory_search`. Reasoning:

1. **Same signal, different surface**: the hub-set IS the grid's current cluster topology. v0.1 proved it's a useful reranker; v0.2 just applies it one layer earlier in the write→link decision.
2. **Structural co-occurrence, not semantic similarity**: I considered embedding the new content server-side and ranking candidates by cosine. Rejected — adds 2GB RSS + 350ms/save to the MCP hot path, and it's the wrong abstraction. Continuity isn't about "this new note is semantically like X"; it's about "this new note belongs to the same attractor as recent activity, so wire it to other attractor members." HashSet membership is the right primitive.
3. **Zero new infrastructure**: `apply_seed_boost` and `seed_boost_keys` already exist (line 9302–9388). One function call inserted into `build_proactive_hint`.

## Non-goals (deferred)

- **Query-time context injection** (boost candidates by which hub the user's *most recent search* hit). Requires per-session state in agent-bridge, larger change.
- **Graded boost** (basin_size or distance-weighted). Stick with binary 1.20× to mirror v0.1.
- **Path A (32-d) signal fusion**. Future v0.3.
- **Auto memory_link execution**. v0.2 still only *suggests*; user/agent decides whether to call `memory_link`.

## Architecture

```
memory_save tool invoked
  └─ store.memory_save(rec)              [unchanged]
  └─ build_proactive_hint(...)
      ├─ store.memory_neighbors(key)      [unchanged — already-linked filter]
      ├─ build OR query from tags+content [unchanged]
      ├─ store.memory_search_hybrid(...)  [unchanged]
      ├─ apply_seed_boost(hits)           ★ NEW (v0.2 step 1)
      ├─ filter (self, already-linked)    [unchanged — but order changed by boost]
      ├─ take(3)                          [unchanged]
      └─ format "consider memory_link: …" [unchanged]
```

Key invariant: `apply_seed_boost` is fail-soft and idempotent. Empty boost set (no state file, kill switch on, no hub_clusters) ⇒ pass-through. Non-empty ⇒ rerank by 1.20×. So if Path B sidecar dies, v0.2 degrades to v0.1-without-rerank (= original behavior) without error.

## Implementation steps & verification targets

### Step 1 — wire apply_seed_boost into build_proactive_hint

**Change**: one-line addition in `crates/bridge/src/mcp_tools.rs` at ~line 2917, after the `memory_search_hybrid` call:

```rust
let hits = store
    .memory_search_hybrid(&query, &tags_empty, 6, 60.0, 3)
    .await
    .unwrap_or_default();
let hits = apply_seed_boost(hits);   // ← NEW
```

**Verification target**:
- Build green (`cargo build --release --bin agent-bridge`)
- Existing 68 tests still pass (`cargo test -p agent-bridge`)
- Manual A/B: pick a known hub member key as `memory_save` content (e.g., contains references to memories already in hub_clusters). With boost ON, hint suggestions should overlap hub_clusters near_keys more than with boost OFF.
- Negative test: when state JSON is missing or empty, hint output is bit-identical to pre-v0.2.

### Step 2 — SKIPPED (redundant with v0.1 tests)

Original plan: add unit test asserting hub-member candidates rank higher in hint suggestions. Discarded after implementation: v0.1's `seed_boost_applies_factor_and_resorts` already covers the reorder semantics, and v0.2 only calls the same function in a new location — a v0.2-specific test would duplicate v0.1 coverage. The full hint-pipeline integration (which IS unique to v0.2) is heavier than a unit test deserves; folded into Step 3 instead.

### Step 3 — A/B audit harness (now also covers Step 2's intent)

**Change**: extend `/tmp/path_c_ab_test.py` (the v0.1 verifier) to also exercise `memory_save` with a synthetic record. Compare proactive_hint output ON vs OFF.

**Verification target**:
- Script prints two hint strings (boost on/off) and a diff
- Hub members appear earlier in ON than OFF for at least one synthetic case
- No exception when the seed sidecar is offline (graceful degradation)

### Step 4 — deploy + dogfood

**Change**: same recipe as v0.1 — build to `/tmp/agent-bridge-pathc-v02/`, copy over `~/Projects/agent-bridge/target/release/agent-bridge`, restart Claude Code.

**Verification target**:
- After deploy + restart, save a real test memory; confirm proactive_hint references hub members when applicable.
- Run for 1–2 sessions; observe whether suggested links feel more "in-context" with recent activity.

## Tuning knobs

- `SEED_BOOST_FACTOR` — already const at 1.20. v0.2 inherits.
- `AGENT_BRIDGE_SEED_BOOST_DISABLE=1` — already global kill switch. Disables both v0.1 search rerank and v0.2 hint reorder.
- The hybrid search `limit=6, expand_top=3` — could raise to 10/5 in v0.2.x if hub-members are rare in the candidate set after FTS.

## Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Hub-set is empty most of the time (sidecar offline / fresh install) | Low | Pass-through fallback, identical to today's behavior |
| Hub members dominate hint suggestions, masking topical relevance | Medium | Limit boost to 1.20×; FTS still primary ranker; user observes for 1–2 sessions before tuning |
| New record's `key` is itself a hub member (would self-boost) | Low | `build_proactive_hint` already filters `h.record.key != key` after boost |
| Cache invalidation lag (stale hub set) | Low | mtime check per call, cache rebuild on Path B sidecar 60s tick |

## Success criterion

Subjective: after 1 week of dogfood, future-Claude's proactive_hint suggestions feel "more like the active topic" than baseline. Hard to A/B test rigorously since each save is a one-shot.

Objective:
- A/B harness shows non-trivial reordering on at least one synthetic save case
- No regression in existing 68 tests
- Memory `memory_neighbors` density (edges per record) trends up over sessions vs pre-v0.2 baseline (may take weeks of organic use to measure)

## Open questions

- Should v0.2 also boost `memory_link` SEARCH for related-record suggestions, beyond `memory_save`? Currently `memory_link` is direct user invocation — no auto-suggest. If a `memory_link_suggest` tool is added later, same pattern applies.
- Path A's 32-d grid produces a different (smaller, less-pruned) hub topology. Should v0.3 union both? Tradeoff: Path A is currently unused as actuator input.

## References

- v0.1 design + deploy recipe: memory `lesson_path_c_actuator_v01_design_and_deploy_recipe`
- Stage A code: `agent-bridge-seed/perception_filter_sidecar.py` (commit `86ce5f3`)
- Stage B v0.1: `crates/bridge/src/mcp_tools.rs` (commit `abfcbb6` + `acb5c28`)
- v0.1 A/B verifier: `/tmp/path_c_ab_test.py`
- Live state JSON: `~/Projects/agent-bridge-seed/state_pf/perception_filter_state.json`
