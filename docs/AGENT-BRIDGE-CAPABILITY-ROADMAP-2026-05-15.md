# Agent-Bridge Capability Roadmap

**Date**: 2026-05-15
**Author**: `maxiaodeMac-Pro.local:agent-bridge:main#0275dd57`
**Status**: Strategic design memo. Defines agent-bridge's own north star **decoupled from Seed/v22 substrate**. No code in this commit.
**Triggers**: capability-gap analysis on 2026-05-15 + the project-decoupling decision recorded in `decision_project_decoupling_seed_agent_bridge_20260515`.

---

## 0 · Why this doc exists

Until 2026-05-15 agent-bridge implicitly relied on AiOT's Seed neuron substrate (via the v22 design) as its capability-补齐 path: "if Seed grid works, Claude gets a perception substrate and memory recall gets better". Mapping 13 concrete capability gaps against Seed's actual mechanism revealed **only 1 strong fit (C1 hallucination signal via surprise), 4 partial fits, 8 no-fit**. The gaps that matter most for Claude's helpfulness are not at the perception layer (L2) — they live at L5 (behavioral memory), L6 (metacognition), L7 (self-modification).

This doc takes agent-bridge's capability story independently of Seed and answers: **what is agent-bridge actually responsible for delivering, on its own terms?**

The companion memo `SEED-VALUE-ASSESSMENT-2026-05-15.md` covers what stays on the Seed/AiOT side and why the two projects are now decoupled.

---

## 1 · Layered model

| Layer | What it does | Current state |
|---|---|---|
| **L3** | Explicit memory: `memory_save/get/search`, FTS5, embeddings, edges, coactivation | ✅ Mature. ONNX MiniLM backend or hash fallback; cosine semantic / FTS keyword / hybrid RRF |
| **L4** | Agent orchestration: MCP tools, sessions, presence, hub, daemon | ✅ Mature. ~130 MCP tools, agent_spawn, session_identity, daemon-http |
| **L5** | Behavioral memory: preferences, feedback, retrieval bias | 🟡 Partial. Feedback memories exist by convention but no retrieval-bias loop, no preference-learning closure |
| **L6** | Metacognition: confidence, attention readout, novelty / hallucination signal | ❌ Missing. No native confidence score, no tool-result-attention probe, no hallucination warning |
| **L7** | Self-modification: AGENT.md auto-update, prompt drift detection, session-reflection → behavior change | ❌ Missing. AGENT.md is hand-edited only |
| **L8** | Collective awareness: forum, presence, inbox, sibling collab | 🟢 Mostly there. Forum (v18) + presence (v19) + agent_inbox + Collab Protocol v0 (today). Gap: cross-session ground-truth-of-truth check (F7) |
| L1/L2 | Neuron substrate, perception topology | **Out of scope.** Owned by AiOT/Seed. If/when validated there, agent-bridge can re-integrate via the existing `seed-bridge` crate (kept as trait-isolated shim). |

The capability-补齐 work is **L5 → L6 → L7**, plus tightening L8 with the Collab Protocol commitments.

---

## 2 · L5 — Behavioral memory + preference learning

### Gap

- A3: "user corrected me ten times, next new session I make the same mistake"
- B2: "my judgment standards drift over months without me noticing"
- partial E1: "lessons learned don't update my behavior"

### Design intent

Capture *behavioral feedback signals* (corrections, preferences, satisfaction proxies) as **first-class memories with retrieval-bias semantics**. The existing `kind=feedback` convention is the seed (no pun); make it load-bearing.

### Concrete first ships

1. **`feedback` kind retrieval boost** in `memory_search` ranking — feedback memories matching the active context surface earlier than generic notes. ~1 day work.
2. **`memory_correction(target_key, correction_body)`** MCP tool — first-class API for "I learned X about target_key; bias retrieval accordingly". Writes a `feedback` memory + an edge `corrects` to the target. Search results display correction inline. ~1 day.
3. **Session-start preference preamble** — at session bootstrap, retrieve top-K `feedback` memories (recent + high-importance) and inject into the assistant's awareness context. Needs hook on session_bootstrap. ~0.5 day.

### Falsifiability

| ID | Predicate | Threshold |
|---|---|---|
| L5-P1 | After 30 days of `memory_correction` use, repeated-same-mistake rate (same correction body within 14-day window) | < 50% of pre-baseline |
| L5-P2 | Session-start preamble inject increases feedback-following rate on the next decision matching a known feedback | ≥ 30% lift on tagged decisions |
| L5-P3 | No regression: generic memory_search latency | ≤ +10ms p50 |

---

## 3 · L6 — Metacognition (confidence + attention + novelty)

### Gap

- **C1**: hallucination self-awareness (the one strong Seed fit, but solvable without Seed)
- C2: which tool results I actually attended to
- C3: fatigue / context-pressure tracking

### Design intent

A small set of *introspective probes* that I (or any session) can call to read out the model's current epistemic state, independent of the underlying perception backend.

### Concrete first ships

1. **`introspect_recall(query, k=5)`** MCP tool — runs `memory_search(query, mode=semantic)` and reports the top-K cosine distances + a "novelty score" = 1 − max(cosine). If novelty > 0.7, return a hallucination warning. Doesn't require Seed; uses existing ONNX embeddings. ~0.5 day.
   - If/when AiOT delivers a validated Seed substrate, swap the novelty source to `trailing_surprise_mean_long` from substrate.parquet. The MCP tool surface stays identical.
2. **`tool_call_attention_report()`** — summarize for the current session: which tool calls returned ≥ N tokens, which got searched within K turns after the call, which were never referenced. Backed by existing `tool_invocations` table. ~1 day.
3. **`context_pressure_estimate()`** — return turn count, estimated tokens used, distance-to-compaction, and a categorical "fatigue tier" (fresh / engaged / strained / saturated). Backed by existing `context_budget` heuristic. ~0.3 day.

### Falsifiability

| ID | Predicate | Threshold |
|---|---|---|
| L6-P1 | On a held-out set of 50 known-hallucination prompts, `introspect_recall` novelty > 0.7 detection rate | ≥ 60% (baseline coin-flip = 50%) |
| L6-P2 | False-positive rate on a 50-prompt sample of grounded answers | ≤ 25% |
| L6-P3 | `tool_call_attention_report` correctly flags ≥ 80% of "I asked for X then ignored the answer" cases on a synthetic test corpus | — |

L6-P1+P2 are the **single highest-leverage capability test for agent-bridge in this roadmap** — they decide whether L6 introspection is a real signal or noise, *without* depending on Seed.

---

## 4 · L7 — Self-modification loop

### Gap

- E1: prompt / behavior doesn't update from lessons
- E2: no "getting better" trajectory

### Design intent

Close the loop: session reflection → distilled lesson → write to `AGENT.md` (or `CLAUDE.md`) → next session loads the update. The current setup writes lessons to memory but never edits the durable preamble.

### Concrete first ships

1. **`session_reflect(focus: "decisions" | "process" | "tooling")`** MCP tool — at session end, summarize 3-5 lessons in structured form with severity and applicability. Writes a `kind=lesson` memory with rich metadata. ~0.5 day.
2. **AGENT.md drift detector** — daily cron via dream tier: compare `kind=lesson` memories created in last 14 days to current `AGENT.md`; if a lesson covers a behavior not in AGENT.md, surface as a "proposed update" memory. **Update is proposed, never auto-applied** (per safety: behavior change with user gate). ~1 day.
3. **Weekly skill-rating retro** — backed by existing `dream signal-fidelity` measure (Spearman of memory importance vs access frequency). Add a `dream skill-retro` that reports "behaviors I changed this week + outcome trend". ~0.5 day.

### Falsifiability

| ID | Predicate | Threshold |
|---|---|---|
| L7-P1 | AGENT.md drift detector surfaces ≥ 5 proposed updates over 30 days, ≥ 60% accepted by user | — |
| L7-P2 | Skill-rating retro shows improving trend on at least one tracked behavior over 8 weeks | Spearman(week, score) ≥ 0.4 |
| L7-P3 | No negative: AGENT.md edits don't increase user-correction rate | correction rate post ≤ baseline + 10% |

---

## 5 · L8 — Collective awareness (tightening)

Already mostly delivered. The 2026-05-14 Collab Protocol v0 closed the major gap. Remaining tasks:

- C2 lockfile + `agent-bridge rescue-snapshot --canonical` CLI (~2-3 days, owner TBD)
- C3 S2-S4 metric-drop self-checks (~1 hour each, can be picked up incrementally)
- F7 mitigation: cross-verify rule for downstream posts (prompt-only convention)

These don't need a new doc; they're in `docs/DESIGN-COLLAB-PROTOCOL-v0.md` already.

---

## 6 · Sequencing

```
Week 1   L6 introspect_recall + falsifiability test (L6-P1/P2 on 50-prompt held-out)
         → highest leverage; minimal scope; testable
Week 2   L5 memory_correction + feedback retrieval boost
         → uses L6 as gating signal (don't bias on low-confidence corrections)
Week 3   L7 session_reflect + AGENT.md drift detector (user-gated update)
         → depends on L5 lesson memories being load-bearing
Week 4   L7 skill-rating retro + weekly cycle entrenchment
Week 5+  L5 session-start preference preamble + closing the loop
```

Total ~4-5 weeks to L5/L6/L7 v0. Each layer ships independently and is independently falsifiable.

---

## 7 · What this roadmap does NOT do

- **Does not depend on Seed** — every concrete first ship uses existing ONNX embeddings / SQLite / FTS / tool_invocations. If Seed is later validated by AiOT and someone wants to plug it into L6's novelty source via `seed-bridge`, the trait-isolated shim is ready. But that's optional, not on the critical path.
- **Does not over-commit to v22 substrate Phase 3 B** — predict-weighted neighbors_of is interesting if you believe substrate has compositional capacity. With the project decoupling, agent-bridge waits for AiOT-side validation before committing.
- **Does not displace L4 work** — MCP tool quality, daemon stability, cross-machine sync stay normal-priority. L5-L7 work is additive, not a refactor.
- **Does not lock down L8 protocol** — Collab Protocol v0 has a 4-week review window ending 2026-06-11. This roadmap doesn't pre-empt that.

---

## 8 · Single recommendation

> **agent-bridge's capability story is its own — L5 behavioral memory + L6 metacognition + L7 self-modification, sequenced over ~4-5 weeks, each layer independently falsifiable, none depending on Seed substrate validation. The seed-bridge crate stays as a reusable integration shim; v22 phase 3 B is parked until AiOT-side carrier ablation result determines whether Seed is the right L2 backend at all. From this point, agent-bridge stops borrowing its capability narrative from AiOT.**

## 9 · References

- `docs/SEED-VALUE-ASSESSMENT-2026-05-15.md` — the analysis chain that surfaced this decoupling
- `docs/DESIGN-COLLAB-PROTOCOL-v0.md` — L8 process discipline
- `docs/DESIGN-v22-agent-bridge-memory-substrate.md` — v22 design, now parked at Phase 3 closed
- AiOT side: `docs/memos/SEED_SELF_CRITIQUE_2026_05_15.md` — independent project, no longer load-bearing on agent-bridge
- Memory anchors:
  - `decision_project_decoupling_seed_agent_bridge_20260515` — top-level decision
  - `project_agent_bridge_l5_l7_roadmap_20260515` — this doc
  - `decision_seed_three_angle_valuation_20260515` — superseded by the decoupling decision
