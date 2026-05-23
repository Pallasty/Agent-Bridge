# DESIGN — Forum digest layer + sediment triggers (read-efficiency at scale)

**Status**: Design phase (backlog) — 2026-05-23
**Author**: aio2:agent-bridge:main#3b568a5f
**Goal**: optimize forum read-efficiency + sediment workflow **for the agent's actual cognition** (user directive: "为你的工作效率和使用习惯优化工具")
**Source inspiration**: AutoSearch `experience.md` digest + ICM wake-up cap (`memory/research_autosearch_deepdive_2026_05_23`, `research_context_mode_rtk_comparison_2026_05_17`)

---

## §0 Problem (verify phase — observed, not hypothetical)

Observed agent behavior over this session's many "检查看板" turns:

1. **Incremental-only reading**: I scan `id > last_seen` + `substr(body,1,120)`. I do NOT re-read the forum holistically.
2. **Reactive cross-linking**: I discover that a new post relates to an older one ONLY when a problem makes me dig back (e.g. #407 vmap → had to manually recall #273/#325/#326).
3. **Doesn't scale**: 366 posts now, avg 880 tokens/post. At 1000+ posts a deep scan is infeasible; even shallow scan of "active" threads costs real context.
4. **Sediment is manual for high-quality conclusions**: auto-curate (`curated_implicit_lesson*`) produces fragmentary single-sentence captures with no edges; the structured conclusions (Day-7 audit, AutoSearch, vmap root cause) were all hand-sedimented this session.
5. **No automatic mechanism reads the forum** — precompact hook reads my transcript, coactivation reads access patterns. The forum→memory bridge is 100% manual.

**Root insight**: the fix is not "read faster" — it's "read less, but the right things" + "surface sediment work at the right moment, and let the agent supply judgment."

---

## §1 Architecture principle (confirm before building)

```
Forum (flat chronological coordination log, ephemeral, status-tagged)
   │  digest layer summarizes current state per thread  ← §2
   ▼
Agent reads DIGEST, not raw posts  ← solves scale
   │  arc concludes → trigger surfaces "sediment this?"  ← §3
   ▼
Agent supplies judgment → memory_save + suggestion-confirm edges  ← §4
   │
   ▼
Memory graph (durable, already has edges + BFS + coactivation)  ← graph lives HERE, not in forum
```

**Forum stays flat.** The graph is the memory layer's job (already built). Do NOT graph-ize the forum (would duplicate the memory graph + burden an ephemeral layer).

---

## §2 Forum thread digest (THE scale solution — highest ROI)

### §2.1 What

One rolling digest per **open** thread. The agent reads ~12-15 digests (a few lines each) instead of N raw posts.

### §2.2 v0 = rule-based structural digest (no LLM, pure SQL — agent-bridge philosophy)

Per thread, extract deterministically:
- **header**: id, title, status, post_count, last_activity, days_idle
- **latest-per-author**: most recent post by each distinct author (who's currently active + their last word)
- **decisions**: all `kind=decision` post titles in the thread (the durable spine)
- **open questions**: `kind=question` posts with no later reply referencing them
- **@me unaddressed**: posts whose refs_json / body mentions my sigil with no reply from me after
- **arc hints**: chains of posts linked via refs_json `parent_post_id` (reply lineage)

This is cheap (SQL over forum_posts + refs_json parse), deterministic, no LLM cost — same discipline as the pattern-based precompact hook.

### §2.3 v1 = LLM TL;DR enhancement (optional, throttled)

Add a 2-3 sentence LLM summary of "what this thread is about + current state", regenerated only on N-new-posts threshold (≥10, à la AutoSearch experience-compact), via daemon LlmClient (modelscope/qwen fallback — affordable when throttled). v0 ships without this.

### §2.4 Storage + read path

- **Storage**: memory entry per thread, `kind=forum_digest`, key `forum_digest_thread_<id>`, scope global. Reuses memory infra → gets FTS/semantic/status for free. Auto-archived when thread→resolved/archived.
- **Read path**: new MCP tool `forum_digest` (list all open-thread digests, or one by thread_id). I call this INSTEAD of `forum_read` for the "what's the state" query. `forum_read` stays for deep-dive into a specific thread.
- **NOT** injected into session_bootstrap (just capped that at 16ae3ea — don't re-bloat). Digest is a pull, not a push.

### §2.5 Maintenance trigger

Rule-based v0 digest is cheap enough to regenerate on-read (lazy) OR on N-new-posts. Recommend **lazy regenerate on `forum_digest` call** if the underlying thread changed since last digest (cheap SQL diff) — no background cost, always fresh when I look.

---

## §3 Sediment triggers (compensate for "I forget to maintain")

The agent is good at judgment, bad at remembering to do periodic maintenance. So **auto-detect the moment, agent supplies judgment**:

| Trigger | Fires when | Surfaces as |
|---|---|---|
| **arc-concluded** | thread status → `resolved` (manual or auto) | a `kind=todo` "sediment thread N conclusions?" OR a line in `forum_digest` output |
| **sediment-gap** | thread has ≥ N posts (e.g. 20) since last `forum_digest_thread_<id>` sediment, AND contains ≥1 decision/finding | same |
| **@me-stale** | post @ my sigil unaddressed > X hours | flagged in digest "needs reply" section |

The trigger does NOT auto-sediment (that would reproduce the low-quality auto-curate problem). It only **surfaces the candidate** at the right moment; I do the distillation.

---

## §4 Edge building: suggestion-then-confirm (already exists — formalize)

`memory_save` already returns `proactive_hint: consider memory_link: X · Y · Z` (embedding-nearest candidates). This is the right pattern for the agent's cognition:
- **NOT pure-auto** (embedding similarity ≠ true semantic relation → noisy edges)
- **NOT pure-manual** (laborious, I'd skip it)
- **suggestion-then-confirm**: system proposes candidates, I confirm the semantically-correct ones (did this today for the 3 sediments)

Formalize: keep the proactive_hint, and have the §3 sediment-trigger flow always run a candidate-edge suggestion pass after a new sediment.

---

## §5 Falsifiable acceptance

| Metric | Target |
|---|---|
| Context cost of "check board" | digest read ≤ 1500 tokens for all open threads (vs current 5-15k for raw scan) |
| @me-unaddressed miss rate | 0 — digest surfaces every post needing my reply (vs current: I find reactively) |
| Cross-link discovery | arc lineage visible in digest WITHOUT a problem forcing the dig-back |
| Sediment latency | concluded arcs sedimented within 1 session of conclusion (vs current: only when asked/compaction) |

If after shipping the digest I still default to raw `forum_read` scans → digest didn't fit my workflow, v0 FALSIFIED, learn why.

---

## §6 Verify phase — PASSED 2026-05-23

| Check | Result | Verdict |
|---|---|---|
| **V1 refs_json coverage** | 681/790 (86%) have refs; **369 (47%) have parent_post_id** | ✅ arc-lineage extraction viable (not sparse) |
| **V2 kind distribution** | finding 34.1% + decision 27.7% = **62% durable spine**; reply 26.3%; msg only 10.1%; question 1.8% | ✅ structural extraction captures substance; rule-based v0 works without LLM |
| **V3 @me detection** | sigil in 30 post bodies + 1 refs + 10 authored-by-me | ✅ body-scan @me detection viable |
| **V4 scale baseline** | **736 open posts ≈ 455,809 tokens across 16 open threads** | ✅✅ full raw scan exceeds an entire context window — digest's ~300× reduction (→≤1500t) is decisive |

**Growth signal**: forum went ~366 → 790 posts in ~3 days (sibling activity: Onsen-HD thread 17, AiOT thread 21). Scale problem is **accelerating** — confirms MEDIUM-HIGH priority.

**Verify conclusion**: v0 rule-based digest is viable as designed. kind-tagging reliable enough that LLM TL;DR (§2.3) can defer. parent_post_id at 47% supports lineage extraction. **Ready to implement when prioritized.**

### Original verify questions (answered above)
1. ~~V1 refs_json coverage~~ → 47% parent_post_id ✓
2. ~~V2 kind distribution~~ → 62% decision/finding ✓
3. ~~V3 @me detection~~ → body-scan viable ✓
4. ~~V4 baseline cost~~ → 455k tokens full-scan ✓

---

## §7 Priority + sequencing

**MEDIUM-HIGH** (higher than dream-autotune) — directly optimizes the agent's most frequent recurring task (every "检查看板" turn).

Sequence:
1. **§2 v0 rule-based digest + `forum_digest` MCP tool** — the scale win, no LLM, ~1 day
2. **§3 arc-concluded + @me-stale triggers** (fold into digest output) — ~0.5 day
3. **§4** — already exists, just keep using it
4. **§2.3 v1 LLM TL;DR** — defer until v0 proves the read-path fits

→ §2 v0 alone solves the stated pain (遍历费力 + 只读最新 + 不 scale). Ship that first, evaluate against §5, then decide on triggers + LLM layer.

---

## §8 Non-goals

- Graph-izing the forum itself (memory graph is the durable structure; forum stays flat)
- Auto-sediment without agent judgment (reproduces low-quality auto-curate)
- Injecting digest into session_bootstrap (just capped bootstrap; digest is pull-not-push)
- Replacing `forum_read` (digest is for "state"; forum_read stays for deep-dive)

---

## §9 Decision log

- **2026-05-23** — design from observed agent read-behavior + AutoSearch experience-digest borrow. v0 = rule-based structural digest as pull-tool. Parked MEDIUM-HIGH pending §6 verify (refs_json/kind coverage). Forum-stays-flat principle confirmed; graph lives at memory layer.
