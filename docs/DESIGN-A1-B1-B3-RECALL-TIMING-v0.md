# DESIGN — A1 / B1 / B3 Recall Timing v0

**Date**: 2026-05-17
**Author**: `maxiaodeMac-Pro.local:agent-bridge:main#0275dd57`
**Status**: design draft, awaiting sibling cross-check before act phase
**Gaps addressed**: A1 (cross-session continuity), B1 (long-term project state), B3 (settled-design re-do)
**Discipline**: §6.5 rule 1 Form A; rule 2 thresholds locked in §5; rule 3 exit plan in §6
**Predecessors**:
- `docs/MONTHLY-GAP-COVERAGE-AUDIT-2026-05-16.md` §8 working defs
- `crates/bridge/src/hooks/ab-memory-hook.sh` (UserPromptSubmit injection, one-shot since `464e046` 2026-04-27)
- `crates/bridge/src/mcp_tools.rs:6677` (L5-P3 feedback preamble)
- `crates/bridge/src/mcp_tools.rs:4157` (`build_proactive_hint` on save/get)

---

## 0 · TL;DR

A1, B1, B3 are three surface manifestations of one root: **memory auto-recall is session-start one-shot, never re-fires within a session**. A second root surfaced during verify: when the agent does query, FTS5 misses ~59% of the time (7d window, 17 searches). Together they explain "data is there but doesn't reach the agent at the right time".

This memo proposes three timing-targeted interventions sharing one substrate:

| Gap | Timing | Intervention | §5 predicate |
|---|---|---|---|
| A1 | mid-session, every turn | Soften one-shot lock to topic-distance + cooldown re-fire | P-A1 |
| B1 | query time | Project-state digest channel inside `session_bootstrap` | P-B1 |
| B3 | save time | Preflight on `memory_save` kind=decision: flag prior cosine-similar decisions | P-B3 |

Three independent falsifiable predicates. Locked thresholds per §6.5 rule 2. If 2 of 3 FALSIFY → rule 3 reframe.

---

## 1 · Verify findings

### 1.1 One-shot lock (root cause #1)

`ab-memory-hook.sh:122-124` since commit `464e046` (2026-04-27):

```bash
LOCK="/tmp/ab-mem-injected-${SESSION_ID}"
[[ -f "$LOCK" ]] && exit 0
touch "$LOCK"
```

The UserPromptSubmit hook ran on **every prompt** by design (it's bound to that event in Claude Code settings), but exits at line 123 on every prompt after the first within a session. Lock files for past sessions confirm intended behavior: each session gets a single top-20-by-static-rank injection, then nothing for the rest of the session, regardless of topic drift or session length.

The choice was deliberate — context inflation was the concern. But the consequence is that A1 (forget what we did last week), B1 (multi-week project state), and B3 (re-do already-settled design) all share this failure: any topic shift mid-session has no recall response.

### 1.2 Query brittleness (root cause #2)

`memory_query_log` past 7 days:

```
source              count   avg_hits   misses (hit_count=0)
mcp:memory_search   17      2.5        10/17 = 59%
mcp:memory_get      5       0.8        1/5 = 20% (key unknown)
palace_viewer:click 15      1.0        0
```

Two signals:

1. **Agent rarely queries on its own** — 17 searches in 7d across all sessions, ~2-3/day. Without a trigger reminding the agent that memory exists, default behavior is "answer from in-context content".
2. **When queried, FTS5 misses majority of the time** — 59% miss rate. FTS5 keyword matching is brittle to rephrasing; semantic search (`mode=semantic`) is on-demand and rarely invoked.

### 1.3 Existing infra inventory

| Layer | When | Coverage |
|---|---|---|
| `MEMORY.md` auto-load (Claude Code kernel) | every session | index titles (≤150 chars/row) |
| `ab-memory-hook.sh` UserPromptSubmit | first turn only (lock) | top-20 by static rank (`access*86400 + updated_at + importance*1e7`) |
| `session_bootstrap` MCP | on-demand | query-aware semantic + L5-P3 feedback preamble |
| `memory_save.proactive_hint` | write time | top-3 graph + FTS5 neighbors |
| `memory_get.proactive_hint` | read time | same |
| L5-P3 feedback preamble | inside `session_bootstrap` only | top-K feedback by importance + 30d half-life |

**No** mechanism fires mid-session on its own. **No** mechanism intercepts before a decision write.

---

## 2 · Mechanism design

### 2.1 Shared primitive — prompt-embedding diff

All three interventions need a cheap "how different is the current topic from what we last injected?" signal. Proposal:

- On each UserPromptSubmit, embed the prompt via existing `EmbeddingBackend` (ONNX MiniLM, ~25 ms).
- Cache the most-recent injection's content centroid as `last_injection_embedding` (computed once per injection).
- Topic-distance = `1 - cosine(prompt_embedding, last_injection_embedding)`.

Why cosine, not LLM judging: L6 v0/v2/Option E all FALSIFIED on LLM-as-judge / token-overlap dimensions. Cosine drift is a different geometric signal — we don't need to know **whether** the recall is good, only **whether topic has shifted**. False positives here cost context tokens, not correctness; false negatives cost a missed injection. Both bounded.

### 2.2 A1 — UserPromptSubmit topic-aware re-fire

Replace the unconditional one-shot lock with a conditional re-fire gate:

```
re-fire IF
    (turn_number == 1)
    OR (turn_number - last_injection_turn) >= COOLDOWN_TURNS  [time/turn fallback]
    OR (topic_distance >= DRIFT_THRESHOLD)                    [drift trigger]
```

Defaults: `COOLDOWN_TURNS = 8`, `DRIFT_THRESHOLD = 0.45` (placeholder; calibrated in act phase 5.4).

Injection payload (existing pipeline, lighter K):

- First fire: top-20 static (unchanged from current)
- Re-fires: top-8 semantic-ranked vs current prompt embedding (smaller, focused)

Storage: append-only `/tmp/ab-mem-injected-${SESSION_ID}.state` with `{last_injection_turn, last_injection_embedding_b64}` so the gate stays cheap (~5 ms read).

### 2.3 B1 — project-state digest

`session_bootstrap` and the hook both gain an optional "project state digest" block when `cwd` resolves to a known project. Block content:

- Latest 3 `kind=decision` rows for project (by `updated_at`)
- Latest 1 `kind=session_handoff` for project
- 3 most recently-accessed `kind=project` rows for project

Always 5–7 rows, hard cap. Surfaces the "what's the current state" answer **without** the agent having to query.

### 2.4 B3 — design-redo preflight

`memory_save` for `kind IN {decision, finding, design}` triggers a cheap preflight:

1. Embed incoming `content[:512 chars]`.
2. Cosine-rank against project-scoped active memories of same kind set.
3. If any prior memory has cosine ≥ `REDO_THRESHOLD` (0.75 placeholder, calibrated in act), emit a `prior_decision_warning` field in the save response.

Save still succeeds — this is informational, not blocking. Falsifies cleanly: we measure whether warned rows in practice are dupes vs novel.

---

## 3 · Why three interventions, not one

The temptation is to consolidate into "per-turn full injection". Three reasons not to:

1. **Context budget**: per-turn injection of top-20 burns ~3-5K tokens × 30 turns × 5 sessions/day. The cooldown + drift gate caps this at ~3-5 re-fires per session.
2. **Different timing**: B3 must fire **before** write (preflight), not at prompt time. B1 wants a stable digest, not a moving topic-driven set. A1 alone can re-fire.
3. **Independent falsifiability**: §6.5 rule 2 — if we bundle them, a single P-fail forces the whole package back to design. Three separate predicates lets two survive while one is reworked.

---

## 4 · Architecture sketch

```
UserPromptSubmit
  └─ ab-memory-hook.sh
       ├─ [A1 gate]  embed prompt → compare to last_injection_embedding
       │              cooldown? OR drift? → inject top-K semantic
       └─ [B1 block] always include project-state digest if cwd known

memory_save (MCP)
  └─ [B3 preflight]  if kind ∈ {decision, finding, design}
                     → cosine-rank vs project-scoped same-kind active
                     → emit prior_decision_warning if any ≥ REDO_THRESHOLD
```

No new tables. No new MCP tools. Two existing surfaces gain conditional behavior.

---

## 5 · Falsifiable predicates (§6.5 rule 2 — thresholds LOCKED)

All three predicates measured on a **30-prompt × 5-session dogfood corpus** captured in act phase 5.4. Corpus excluded from training of any embedding model (none used during measurement; ONNX MiniLM is pre-trained).

### P-A1 — Mid-session recall lift

**Predicate**: On the 30-prompt corpus, mid-session re-fire injections (turns ≥ 2) lift the rate at which the agent's response references **memory content not in the in-context conversation** by ≥ **15 percentage points** vs the no-re-fire baseline (current one-shot behavior).

**FP gate**: of the re-fired injections, ≤ **30%** are irrelevant — measured as jaccard(injected_memory_tags, turn_response_keywords) < 0.2.

**Decision**: PASS only if both halves hold.

### P-B1 — Project-state digest correctness

**Predicate**: On a hand-labeled subset of 10 "what's the status of X" prompts (from past forum threads), the project-state digest block surfaces the **correct top decision** (per author label) in ≥ **70%** of cases.

**FP gate**: ≤ **20%** of digest rows are project-irrelevant (wrong project scope or kind).

**Decision**: PASS only if both halves hold.

### P-B3 — Design-redo flag rate

**Predicate**: On a synthetic eval of 20 redo-candidate writes (matched decision pairs with cosine ≥ 0.7 by construction), `prior_decision_warning` fires in ≥ **80%** of cases.

**FP gate**: ≤ **25%** of warnings on novel decisions (synthetic novel set N=20).

**Decision**: PASS only if both halves hold. Mirrors the L6 ≥60% / ≤25% gate shape so the discipline frame is identical.

### Rule 2 lock statement

These thresholds (P-A1 15pp / 30%, P-B1 70% / 20%, P-B3 80% / 25%) are **locked**. Any revision after dogfood run requires explicit §6.5 rule 2 fixup commit citing the prior threshold and the reason.

---

## 6 · Rule 3 exit plan — what happens if FALSIFIED

| Outcome | Action |
|---|---|
| 0/3 FAIL | Ship all three. |
| 1/3 FAIL | Ship the 2 that pass; the failing one gets one **reframe** attempt (§6.5 rule 3 first use on this gap set). |
| 2/3 FAIL | Reframe — most likely the failure is on the shared topic-distance primitive. Reframe options: (a) replace cosine drift with explicit keyword-based topic tags, (b) drop drift, keep only cooldown turn count, (c) shelve mid-session injection and accept B1/B3 only. |
| 3/3 FAIL | Shelve. Accept that the right answer is **agent-driven** query, not **system-driven** injection. Document as a finding mirroring L6 shelve. Pivot effort to teaching the agent to query better (e.g. a meta-prompt nudge "consider memory_search" injected at session start). |

---

## 7 · Implementation path (act phase, post-cross-check)

Order matters — earlier steps de-risk later thresholds:

1. **Build dogfood corpus** (~30 min) — extract 30 representative prompts + responses from recent forum/session logs; partition into eval sets per P-A1/P-B1/P-B3. **No code yet.**
2. **B3 preflight** (~2-3 h) — smallest scope, single MCP tool surface change, eval set is synthetic. De-risks the cosine primitive in isolation.
3. **B1 digest block** (~2 h) — pure SQL queries + format. No new primitive.
4. **A1 lock softening** (~3-4 h) — touches the hook (most-changed file), needs the prompt-embedding cache invariant. Last because it depends on (2)'s cosine code being shippable.
5. **Wet-run on corpus, measure all 3 P-* simultaneously** (~1 h).

Total estimate: **1-1.5 days** including measurement. Smaller per intervention than L6 v0 (which was ~2 days).

---

## 8 · Risks identified at design time

- **Context budget overflow** — if A1 fires too often. Mitigation: COOLDOWN_TURNS lower bound 5, and re-fire payload uses top-8 not top-20.
- **Embedding latency** — 25 ms × per-prompt = noticeable in interactive use. Mitigation: embedding is async / pre-warmed; on slow paths the gate falls back to cooldown-only (drift skipped).
- **Threshold tuning loop** — if P-A1 fails at 15pp lift, the temptation is to drop to 10pp. Rule 2 forbids this. The exit is reframe (§6) or shelve, not silent threshold relaxation.
- **B3 FP on iterative design** — a series of refinements on the same topic will all cosine ≥ 0.7 with prior. Mitigation: warning is informational; agent reads it and decides to continue refinement. Not a block.

---

## 9 · Cross-link

- §6.5 audit: `project_monthly_gap_audit_v0_20260516`
- Working defs: `docs/MONTHLY-GAP-COVERAGE-AUDIT-2026-05-16.md` §8
- L6 design discipline precedent: `docs/L6-INTROSPECT-RECALL-V0-RESULT-2026-05-15.md` (rule-3 lineage)
- Existing hook: `crates/bridge/src/hooks/ab-memory-hook.sh:122` (the lock line)
- Existing preflight infra to reuse: `crates/bridge/src/mcp_tools.rs:4157` (`build_proactive_hint`)

---

## 10 · Open questions for sibling cross-check

1. Is `DRIFT_THRESHOLD = 0.45` defensible without a quick calibration probe before locking? (proposal: calibrate against a 20-prompt pair-distance sample in act phase 5.4, then lock.)
2. Should B3 also fire on `memory_correction` writes (kind=feedback path), or only `memory_save`?
3. P-B1's "hand-labeled" subset — who labels? Default = me, owner same as predicate.
4. Should the design-redo warning be opt-out via env (`AB_REDO_WARN_DISABLE=1`) for sibling agents doing iterative work? My lean: yes, since false positives are predictable on refinement chains.
