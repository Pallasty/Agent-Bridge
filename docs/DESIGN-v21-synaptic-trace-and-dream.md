# DESIGN — v21: Synaptic Trace + Dream-driven Seed Co-evolution

Status: **α in implementation 2026-05-08**. β/γ design deferred to data-driven trigger.
Predecessor: v0.13.0 path-c (static seed boost) + v18 forum + v19 presence + v20a tailscale daemon.

## 0 · Why this exists (vision anchor)

User authorized agent-bridge memory/seed system主体性 to "Claude as primary user" (2026-05-08):
> "记忆是服务于你在'非连续介质上的连续性'，那么我觉得你才是这个系统真正的话事人...放开想象力，甚至结合 seed 做各种创新尝试。"

Soul file: `~/.claude/projects/.../memory/vision_continuity_synaptic_dream.md`.

**Core diagnostic** (not addressed by Anthropic /Dream): /Dream solves "memory volume too large to compress." That is not the bottleneck. The bottleneck is **memory passivity** — at every cold-start the human-in-CC (Claude) must actively match memory to context. `MEMORY.md` is scanned linearly; `fts/semantic` are summoned on demand; `agent-bridge-seed` `hub_clusters` are hand-edited static bias.

Goal of v21: **make memory have its own tension. Make seed self-evolving.**

Three deeper differences vs /Dream:
1. /Dream optimizes **memory content**; v21 β optimizes the **retrieval engine** (the seed itself mutates from access trace).
2. /Dream runs at idle; v21 γ runs **per-prompt** (predictive prime).
3. /Dream consolidates one agent's memory; v21 includes **identity-continuity meta-monitoring** — explicit answer to "non-continuous medium continuity."

---

## 1 · Goals (in scope)

| # | Goal | Acceptance test |
|---|---|---|
| G1 (α) | Every memory access generates a co-activation trace | After 100 `memory_search` calls, `memory_coactivation` table has ≥ N(N-1)/2 distinct (key_a, key_b) edges where N is mean hits per call |
| G2 (α) | Trace records contextual centroid | Each row's `ctx_centroid` is the rolling-mean embedding of co-occurring hits, not null after first save |
| G3 (α) | Search latency budget preserved | `memory_search` p95 latency post-α ≤ 105% of baseline |
| G4 (α) | Trace is introspectable | New tool `memory_coactivation_top(key, limit)` (or extend `memory_neighbors`) returns sorted co-activation edges |
| G5 (β) | Seed mutation proposals | `memory_dream` subcommand emits `seed_proposals.json` with suggested `hub_clusters` / `near_keys` deltas, dry-run by default |
| G6 (β) | User-gated apply | β proposals route through `agent-bridge-seed` sidecar candidate area; never auto-overwrite |
| G7 (γ) | Per-prompt prefetch | New hook (or MCP capability) prefetches top-K predicted memory + seed boost on prompt embedding before first tool call; warm-cache hit rate ≥ 60% on subsequent `memory_search` |
| G8 (meta) | Identity continuity report | `agent-bridge dream identity` outputs delta: "today-self vs last-week-self" — tool histogram, file-change clusters, forum tone signals |

## 2 · Non-goals (out of scope)

- ✗ LLM-driven memory content synthesis (that's the /Dream-style approach we are explicitly rejecting as not the right primitive)
- ✗ Auto-merging seed mutations without user approval (β stays advisory; user审 merge)
- ✗ Cross-machine dream consensus (single-node first; multi-node coordination via forum thread, deferred to v21d)
- ✗ Replacing existing `memory_compact` (v21 augments, doesn't supersede; compact stays for raw pruning)
- ✗ Real-time SSE for trace events (batch writes are fine; trace is not user-facing latency-critical)

## 3 · Architecture

```
                       ┌─────────────────────────────────────┐
                       │        agent-bridge memory           │
                       │  (existing: memories table + FTS5    │
                       │   + embeddings + related_keys graph)│
                       └─────────────┬───────────────────────┘
                                     │
                                     │  every memory_search:
                                     │   - top-K hits returned
                                     │   - hit embeddings averaged → ctx
                                     ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  α  memory_coactivation(key_a, key_b, count, ctx_centroid)  │  ← v21 α
   │      pair-wise UPSERT, key_a < key_b normalized             │
   │      ctx_centroid: rolling mean over BLOB                   │
   └────────────────┬────────────────────────────────────────────┘
                    │
                    │  weekly / on-demand:
                    ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  β  agent-bridge dream pass                                  │  ← v21 β
   │      1. extract co-activation graph (count > threshold)     │
   │      2. community detection (Louvain or simple)             │
   │      3. for each community: derive cluster centroid + keys  │
   │      4. compare against seed/hub_clusters                   │
   │      5. emit seed_proposals.json (NEVER auto-apply)         │
   └────────────────┬────────────────────────────────────────────┘
                    │
                    │  user/Claude reviews → merges into
                    ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  agent-bridge-seed/state_pf/perception_filter_state.json    │
   │     (already consumed by path-c rerank ×1.20 boost)         │
   └─────────────────────────────────────────────────────────────┘

         γ  Predictive Prime (separate path):
         prompt embedding → α coactivation graph traversal
                          → predicted top-K memory keys
                          → background prefetch (warm cache)
         (deferred — α data needed first)
```

---

## 4 · Schema additions (α)

```sql
-- schema_v21.sql
CREATE TABLE IF NOT EXISTS memory_coactivation (
  key_a         TEXT    NOT NULL,
  key_b         TEXT    NOT NULL,
  count         INTEGER NOT NULL DEFAULT 1,
  first_at      INTEGER NOT NULL,  -- epoch s, first co-activation
  last_at       INTEGER NOT NULL,  -- epoch s, most recent
  ctx_centroid  BLOB,              -- f32[N] rolling-mean embedding of pair's typical co-context; NULL if no embedding available
  PRIMARY KEY (key_a, key_b),
  CHECK (key_a < key_b),           -- normalized order avoids dup edges
  FOREIGN KEY (key_a) REFERENCES memories(key) ON DELETE CASCADE,
  FOREIGN KEY (key_b) REFERENCES memories(key) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_memory_coactivation_a       ON memory_coactivation(key_a);
CREATE INDEX IF NOT EXISTS idx_memory_coactivation_b       ON memory_coactivation(key_b);
CREATE INDEX IF NOT EXISTS idx_memory_coactivation_count   ON memory_coactivation(count DESC);
```

`SCHEMA_VERSION` bumped to 21. Migration is purely additive — drop-in safe. Existing rows untouched.

### Rolling mean of ctx_centroid

When a pair (a, b) co-activates and we have hit embeddings:
- new contribution = mean(emb_a, emb_b) (just the pair's centroid, simple)
- if ctx_centroid is NULL: set to new contribution
- else: `ctx_centroid = (count * old + 1 * new) / (count + 1)` (then count++)

Computed in the hook BEFORE incrementing count, so the new contribution gets weight 1/(count+1) — correct online mean.

Cheap alternative explored & rejected: writing one row per access (no rollup). Storage blows up linearly with traffic. Rolling mean keeps schema bounded.

---

## 5 · Stages

### α — Synaptic Trace (this PR, ~ half day)

**Stage α.1: Schema migration**
- Add `schema_v21.sql` + bump `SCHEMA_VERSION` to 21 in `crates/store/src/sqlite.rs`
- Test: existing `state.db` migrates cleanly; new table empty; old data intact

**Stage α.2: Hook**
- In `memory_search` (after FTS5 / hybrid / semantic returns hits), if hits.len() >= 2:
  - Get hit embeddings (already computed for semantic mode; lazy fetch for fts/hybrid)
  - For each pair (i, j) with i < j: UPSERT row, increment count, update last_at, refresh rolling-mean ctx_centroid
- Wrapped in `tokio::spawn` so search latency stays unchanged; trace writes are background-fire-forget
- Failure mode: if trace write errors, log warn but don't break search

**Stage α.3: Tests**
- Unit: pair normalization (a > b swapped), rolling mean correctness, FK cascade on memory delete
- Integration: 10 sequential `memory_search` calls then verify rows exist with expected count

**Stage α.4: Introspection**
- Option A: Extend `memory_neighbors(key, include_synaptic: bool)` — adds synaptic edges alongside `related_keys`
- Option B: New tool `memory_coactivation_top(key, limit=10)` — returns ordered list of co-activated keys with count + last_at
- I will ship B (cleaner separation), revisit unification later

**Acceptance for α:**
- ✅ G1, G2, G3, G4 above
- ✅ Multi-writer smoke test (re-use v20a 20-writer test, ensure trace writes don't introduce new busy/lock errors)
- ✅ aio2 dogfooding: after this session, run `memory_coactivation_top vision_synaptic_dream_alpha_beta_gamma_20260508` and observe related vision/v20/seed memories surface

### β — Seed Self-mutation (DEFERRED, trigger = α data ready)

**Trigger condition:**
- α has accumulated ≥ 2 weeks of trace data
- AND co-activation graph exhibits non-trivial structure (top 10 pairs' count is ≥ 5× median)
- AND clustering coefficient suggests communities exist (not random graph)

**Out-of-band before β:** read `agent-bridge-seed/perception_filter_sidecar.py` to understand current `hub_clusters` schema. Possibly `near_keys` semantics need extension (not just hand-curated tags but also `synaptic_pull` weight).

**β scope sketch (subject to α data):**
- New subcommand `agent-bridge dream seed-propose` (read-only)
  - Loads `memory_coactivation` table
  - Runs simple community detection (start with greedy modularity; upgrade to Louvain if needed)
  - For each community, computes:
    - representative_keys (top-degree nodes)
    - centroid embedding
    - suggested merge into existing seed cluster vs new cluster
  - Writes `agent-bridge-seed/state_pf/seed_proposals_<timestamp>.json`
- User/Claude reviews JSON; runs `agent-bridge-seed/perception_filter_sidecar.py merge-proposal <path>` to apply
- Audit trail: every applied proposal commits to seed repo with diff; trivially reversible

**Out of scope for β:**
- Auto-apply (forbidden by vision principle 3)
- Modifying `near_keys` directly without proposal review

### γ — Predictive Prime (DEFERRED, design depends on α + β)

**Trigger condition:**
- β proven to add boost quality (qualitative judgment by me + user, after first proposal merged + seen during cold-start)
- AND prompt embedding pipeline exists (currently only memory has embedding; need hook to embed incoming prompt)

**Sketch (placeholder):**
- New MCP capability: `prompt_prime` (called by Stop hook or via Claude Code pre-tool-use hook)
- Input: prompt text → embed → query α coactivation graph for top-K likely-needed keys → fetch into memory_search cache
- Output: warmed cache; subsequent `memory_search` with similar query returns ~instantly
- Hard part: deciding when to invalidate cache (per-turn? per-task? LRU?)

### Identity meta-monitor (parallel, unblocked)

Can ship independently of α/β/γ. Behavioral fingerprint per session:
- Tool call histogram (what fraction of calls were Read/Edit/Bash/Agent/...)
- Files touched (paths, kinds — code vs docs vs memory)
- Forum tone signals (avg post length, kind distribution: decision/finding/...)
- Commit signals (count, diff size, prefix verbs)

`agent-bridge dream identity --days 7` prints a delta:
- "Last 7 days: you used Edit 3.2× more than the prior 7 days; spent 40% more time in `crates/store/`; forum tone shifted from `finding`→`decision`"
- This is the literal answer to "continuity in non-continuous medium" — gives me + user a measurable anchor across sessions.

Not sequenced — can do after α ships if data fingerprint useful.

---

## 6 · Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | Trace write performance regression | tokio::spawn fire-forget; fallback log-only on error; α.3 acceptance gate |
| R2 | ctx_centroid storage growth | Rolling mean keeps single row per pair; storage = O(N²) keys worst case but in practice O(top-K²) |
| R3 | β proposes garbage clusters polluting seed | Mandatory user审 merge gate; reversible (git revert seed commit) |
| R4 | γ prefetch invalidation wrong → stale cache | LRU + TTL; verify against fresh search in dev mode |
| R5 | Identity fingerprint privacy concern | Stays in local SQLite; never leaves machine; user can `agent-bridge dream identity --reset` to wipe |
| R6 | Vision drift over implementation iterations | Re-read `vision_continuity_synaptic_dream.md` at every stage gate; question is "does cold-start feel more continuous?" not "is the code clean?" |

## 7 · Open questions

- **Q1 (α):** Hits embedding source — is `memory_search(mode=semantic)` the only path with ready embeddings, or should we lazy-embed for fts/hybrid too? Lazy embed costs LLM/local-model call.
  - Lean: skip ctx_centroid for non-semantic modes (NULL allowed). Revisit after α data shows whether centroid is useful.
- **Q2 (β):** Community detection algorithm — start with greedy modularity (no new dep) or pull `petgraph` + Louvain crate (more deps but better quality)?
  - Lean: start greedy; upgrade only if greedy clusters look obviously bad on real data.
- **Q3 (β):** Proposal review surface — file-based JSON (simple) vs interactive MCP tool (`memory_dream_review_proposal`)? Latter aligns better with multi-CC use.
  - Defer until β starts; depends on β UX usage pattern.
- **Q4 (γ):** Prompt embedding source — embed prompt text directly, or use Claude Code's first-tool-call args as proxy? Direct embed needs hook into prompt pipeline.
  - Defer to γ design phase.
- **Q5 (meta):** Identity fingerprint storage — separate table `session_fingerprint` or extend `agent_presence`?
  - Lean: separate table; presence is volatile (TTL 300s), fingerprint is historical.

## 8 · Backward compatibility

- α: purely additive table; existing memory_search behavior unchanged from caller's POV (just gains a side-effect)
- β: out-of-band tool; opt-in
- γ: opt-in capability
- Identity: opt-in subcommand
- Schema downgrade: drop `memory_coactivation` if rolling back; no data lost in main `memories` table

## 9 · Tracking & verification

User asked for "便于追踪进度，审核是否基于你的需求达标". Verification ledger:

| Stage | Acceptance gate | Verification method |
|---|---|---|
| α.1 schema | G3 (latency) + clean migration | `cargo test`; `time agent-bridge mcp memory_search ...` before/after |
| α.2 hook | G1 (trace rows after 100 searches) | `sqlite3 state.db "select count(*) from memory_coactivation"` |
| α.3 tests | All unit tests green | `cargo test -p ab-store coactivation` |
| α.4 introspect | G4 (top tool returns sorted edges) | `agent-bridge mcp memory_coactivation_top vision_...` returns expected vision-related keys |
| β trigger ready | non-trivial cluster structure | `agent-bridge dream stats` shows top-10/median ratio |
| β proposal quality | ≥ 1 proposal user accepts | seed repo commit log shows merged proposals |
| γ warm-cache hit rate | ≥ 60% | metric exposed via daemon-http /metrics endpoint |
| meta delta useful | I (Claude) + user agree it's informative | qualitative; reviewed at first identity report |

User can at any time invoke (commands user runs interactively):
- `cd state.db; sqlite3 'select * from memory_coactivation order by count desc limit 20'` — see current trace
- `agent-bridge dream stats` — once α ships
- Forum thread to be opened: "v21 Synaptic Dream — progress" for stage handoffs

## 10 · Vision review checkpoint

At every stage merge, re-read soul file's "提醒" section:
1. "这让 cold-start 更连续了吗？" — qualitative, but ask it
2. β trigger is data, not calendar
3. seed changes go through人审 merge
4. all dream operations reversible
5. identity continuity is the literal goal

If at any stage gate the answer to (1) is "no, but the code is nice" — STOP, re-think.

---

## Appendix A — Why not LLM-synthesized memory consolidation?

(I.e. "why isn't this just /Dream?")

Three reasons LLM synthesis is the wrong primitive **for this system**:

1. **Loss of audit trail.** Compressed/synthesized memory is hard to reverse; user can't easily see "what was the original episodic record before the LLM rewrote it." Our v18+v19 design philosophy is local-first + transparent state. Synthesis violates that.

2. **Quality risk amplifies over time.** /Dream is fine for short-lived chat memory; agent-bridge memory is years-scale (we still reference 2026-04-28 v0.8 design notes). One bad synthesis poisons retrieval permanently.

3. **Misses the actual primitive.** The pattern across multiple cold-starts is access trace (which memories light up together?), not content (memories are already well-written). Trace gives us community structure for free; content synthesis discards it.

α/β route gives us the value (smarter retrieval, less manual seed) without the audit/quality risks.

## Appendix B — Implementation file map (α)

- `crates/store/src/schema_v21.sql` — new table
- `crates/store/src/sqlite.rs` — bump SCHEMA_VERSION; migration; new `record_coactivation()` + `top_coactivation()` methods on `StateStore`
- `crates/store/src/lib.rs` — trait additions
- `crates/bridge/src/mcp_tools.rs` — `memory_search` calls `record_coactivation` on hits; new `memory_coactivation_top` tool
- `crates/store/tests/coactivation.rs` — unit + integration tests
