# DESIGN — Context Lifecycle Edges (A + C)

**Status**: Phase 1 (verify + design) — started 2026-05-17
**Author**: aio2:agent-bridge:main#3b568a5f
**Source**: Borrowed from [rtk-ai/icm](https://github.com/rtk-ai/icm) (ICM = "Context Mode")
**See also**: `~/.claude/projects/-Data-CascadeProjects-agent-bridge/memory/research_context_mode_rtk_comparison_2026_05_17.md`

---

## §0 Framing

ICM's hook taxonomy:

| Layer | Trigger | What |
|---|---|---|
| L0 PostToolUse | after tool output | rule-based extract (we already have via stop hook) |
| L1 **PreCompact** | before conversation compression | extract memory before lossy compaction |
| L2 UserPromptSubmit | each user message | recall + inject relevant memories |

agent-bridge currently has L0 (`session_finalize`/sync.sh stop hook) and a degenerate L2 (`seed` hook computes `theme_cos` score but does **not** inject). We have **no L1**, and L0 only fires at session end — mid-session compactions silently lose information.

This design closes two "context lifecycle edges":

- **A (PreCompact)**: `agent-bridge hook compact` invoked before Claude Code compresses conversation → lossy extract → `memory_save`
- **C (Bootstrap cap)**: `SessionBootstrapTool` adds `max_tokens` cap to bound what's injected at session start

Both are pure-I/O at lifecycle transitions; neither touches substrate internals (P-α/P-ε independent).

---

## §1 A — PreCompact Hook

### §1.1 Trigger path

```
Claude Code conversation grows → harness detects compaction needed →
  invokes hook command (configured in ~/.claude/settings.json):
    "PreCompact": [{ "command": "agent-bridge hook compact" }]
  → hook reads stdin (= transcript segment to be compacted)
  → hook extracts lossy summary
  → hook calls memory_save (one or more `kind=session_compact` memories)
  → hook exits 0; Claude Code proceeds with compaction
```

**Hook verify needed**: confirm `PreCompact` is a real Claude Code hook name (Anthropic docs §hooks). If not, fall back to detecting compaction via `system-reminder` "Compacted" message and emit via stop-hook-like sidecar.

### §1.2 Extract rules (v0 — no LLM)

Pattern-based, same style as RTK static rules:

| Signal | Action |
|---|---|
| Tool result lines matching `commit [0-9a-f]{7,}` | Extract commit SHA + first line as `kind=event` memory |
| `error:` / `FAILED:` blocks | Extract as `kind=incident` memory |
| User messages starting with verbs `决定 / 选 / 用 / let's` | Extract as `kind=decision` memory |
| Tool calls with `forum_post` body | Extract author + thread_id + first 200 chars as `kind=forum_trace` memory |
| Code edits to `docs/DESIGN-*.md` | Extract path + diff hunks as `kind=design_change` memory |

**Token budget for extracts**: ≤ 200 tokens per extract; ≤ 5 extracts per compaction event.

### §1.3 Output

One or more memories with:
- `kind=session_compact_<subkind>` (e.g. `session_compact_event`)
- `tags` including `compaction:<timestamp>` for traceability
- `dedupe_key=compact:<sha256(content_first_500_chars)>` to skip if extracted before

### §1.4 Falsifiable acceptance

| Metric | Target |
|---|---|
| Hook fires on real compaction | ≥ 95% (10 sessions × N compactions each) |
| `dream replay-audit` after 7 days shows extracted memories accessed | ≥ 30% of extracts touched in subsequent sessions |
| Extracted memories recall@10 vs raw transcript (oracle eval) | ≥ 0.8 |

---

## §2 C — Bootstrap Token Cap

### §2.1 Current shape

`SessionBootstrapTool::execute` returns:
1. Letters block (memories tagged `kind=letter`, no cap)
2. **L5 P3 feedback preamble** (top-5 by score = `importance + 0.3 * exp(-age/30d)`, **no token cap**)
3. Decisions Due block (active decisions, no cap)
4. Possibly more (project status, presence, etc.)

Problem: unbounded → ICM caps at 500 tokens per their wake-up. We're seeing bloat as L5 P3 adds 5 × ~150-char feedback each session.

### §2.2 Proposed

Add `--max-tokens N` (default **N=800**) flag + env `AB_BOOTSTRAP_MAX_TOKENS`:

```rust
// Pseudo
fn render_bootstrap(max_tokens: usize) -> String {
    let mut budget = max_tokens;
    let mut out = String::new();
    for block in [letters, l5_feedback, decisions_due, presence] {
        let rendered = block.render();
        let cost = estimate_tokens(&rendered);
        if cost <= budget {
            out.push_str(&rendered);
            budget -= cost;
        } else {
            // truncate block to fit budget, mark with "[...trimmed N items]"
            let trimmed = block.truncate_to_tokens(budget);
            out.push_str(&trimmed);
            break;
        }
    }
    out
}
```

### §2.3 Ranking within each block

Same per-block ranking as today (e.g. L5 P3 score formula unchanged), but with hard token cap on the combined output.

If budget runs out mid-block, render `[...trimmed N more items — see memory_list kind=feedback]` so the truncation is visible.

### §2.4 Token estimate

Use cheap heuristic: `chars / 3.5` for mixed EN/CJK. Don't call tokenizer — that defeats "fast bootstrap" goal. Same heuristic as `context_budget` MCP tool.

### §2.5 Falsifiable acceptance

| Metric | Target |
|---|---|
| Bootstrap output size p95 | ≤ 800 tokens (vs current uncapped, often >1500) |
| % bootstraps that hit cap (early truncation) | < 30% (else N too low) |
| User-reported "I missed important context" | 0 across 7 days |

---

## §3 Verify phase findings (2026-05-17 — pivot accepted)

### A.1 PreCompact hook — **ALREADY SHIPPED**

`~/.claude/settings.json` already has `PreCompact` → `/home/pallasting/.local/bin/ab-precompact-hook`. Script:
- Locates transcript JSONL from session_id
- Pre-processes Lessons/Decisions/Summary sections (adds `lesson:` / `decision:` markers)
- Calls MCP `session_lifecycle_step(precompact)` = `session_curate` + `session_finalize`
- Tunable: `AGENT_BRIDGE_CURATE_SCORE_THRESHOLD`, `AGENT_BRIDGE_CURATE_DEDUP_JACCARD`

**17 successful fires** in `~/.local/share/agent-bridge/hook-runs.jsonl`. Today's session saw `Memory precompact: +2 memories | curated=2 skipped=0 | session_finalize done`.

→ My §1.2 extract rules **superseded** by the existing curate engine. **A is not a build — it is an audit.**

### A.2 UserPromptSubmit — **HALF SHIPPED**

`~/.local/bin/ab-memory-hook` v3.0 already injects memories on first prompt:
- Always-inject: concept nodes + session_handoff (≤15)
- Then top-20 scope-matching by `kind tier × access × recency × importance`
- Lock file `/tmp/ab-mem-injected-${SESSION_ID}` → **only first prompt of session**

→ **Real gap**: no re-injection on subsequent prompts when theme_cos is high. This was originally Idea B (out of A+C scope). Capture as backlog.

### C.1 Bootstrap output size — **MUCH LARGER THAN ASSUMED**

Live measurement via MCP stdio `session_bootstrap`:

```
bootstrap text: 16834 chars ≈ 4810 tokens
```

Blocks (from first 1200 chars):
- AiOT Soul (trait vector + 256-dim embed summary) ~400 chars
- Agent-Bridge Seed (step / n_alive / spawns / top-3 neurons) ~300 chars
- Perception Filter (filter mode / kept ratio / grid stats) ~200 chars
- + Letters, L5 P3 feedback (5 items), Decisions Due, bootstrap memory rows, γ' wiring section, end markers — ~15000+ remaining chars

→ Original N=800 would cut **5/6** of content. **Need per-block budget, not single cap.**

## §3.5 Revised plan (post-pivot)

| Work | Original | Revised |
|---|---|---|
| A | 3h build PreCompact extract rules | **1h audit**: 7-day precompact triggers + extracted memory access rate; tune `SCORE_THRESHOLD` / `DEDUP_JACCARD` if needed |
| B (new) | not in scope | **backlog**: enhance `ab-memory-hook` to re-inject on high theme_cos with cooldown |
| C | 30min global cap N=800 | **2h per-block budgets**: AiOT 200 / Seed 200 / Perception 150 / Letters 200 / L5 P3 300 / Decisions 200 / Rows 500 / γ' 200 = **1950 tokens p95** (60% reduction from 4810) |

## §3.6 C — per-block budget detail

| Block | Current cost | Target cap | Strategy on overflow |
|---|---|---|---|
| Header (`=== ... ===`) | ~20 chars | unbounded | always render |
| AiOT Soul | ~400 chars (~115t) | **200t** | omit identity embedding top-5 dims; keep fingerprint + trait vector |
| Seed | ~300 chars (~85t) | **200t** | drop one of top-3 neurons if needed |
| Perception Filter | ~200 chars (~57t) | **150t** | drop grid stats if needed |
| Letters | variable | **200t** | render most-recent first, truncate to fit |
| L5 P3 Feedback | 5 × ~150c = ~210t | **300t** | already capped at K=5; reduce K if budget overflow |
| Decisions Due | variable | **200t** | most-recent-due first, truncate |
| Bootstrap memory rows | ~12000c = ~3400t (!!) | **500t** | top-N by `kind tier × score`; show `[...N more — see memory_search]` footer |
| γ' wiring (neighbors-of-recent-seeds) | ~variable | **200t** | top-3 only |
| **Total** | **~4810t** | **~1950t** | hard global cap = 2400t as safety net |

Implementation: extract each block into `Vec<String>` first, measure cost via heuristic `chars / 3.5`, apply per-block cap with consistent trim marker `[...trimmed N items]`.

---

## §4 Plan phase (after verify)

1. **A**: Add `agent-bridge hook compact` subcommand
   - Reads stdin (or `--transcript-path`)
   - Runs pattern extractors (§1.2)
   - Calls `memory_save` per extract via internal store API (skip MCP roundtrip)
   - Effort: ~2h impl + 30min test
2. **C**: Modify `SessionBootstrapTool::execute`
   - Add `max_tokens` param (default 800)
   - Add per-block `truncate_to_tokens()` helpers
   - Effort: ~30min impl + 30min test
3. **Hooks wiring**: update `scripts/hook-install.sh` to register `PreCompact` if hook is valid; or document opt-in in CLAUDE.md
4. **Tests**: 6+ new unit tests covering extract rules + cap truncation

Total impl: ~3-4h end-to-end after verify phase passes.

---

## §5 Risk + non-goals

**Risks**:
- A.R1: Claude Code may not actually have a `PreCompact` hook (verify §3.A1)
- A.R2: Stdin transcript format may be too noisy for pattern extract (verify §3.A2) — fallback: only extract from "Compacted" system-reminder summary
- C.R1: Heuristic token count may overshoot real tokenizer by 20% → set N=800 with margin

**Non-goals**:
- LLM-driven summarization in A (out of scope; v0 is pattern-only)
- Per-user/per-project bootstrap cap tuning (v0 is global)
- Re-architecting `SessionBootstrapTool` (only cap the output, don't refactor)

---

## §6 Future (post-v0, not in scope)

- B (UserPromptSubmit inject) — separate design memo when v0 ships
- D (fuzzy cosine dedup at save) — orthogonal, separate ship
- E (consolidate hint) — orthogonal, separate ship
- F (transcript indexing) — large effort, separate roadmap item
- G (shell_exec compression) — cross-project, evaluate after A+C ship

---

## §7 Decision log

- **2026-05-17 17:xx UTC** — design started, gate awaiting user review before verify §3
- (next: verify outputs land here)
