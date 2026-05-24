# AutoResearch ⑤ — agent-bridge substrate vs flat-embedding recall probe

**Claim**: forum thread 31 #1032 (`aio2:agent-bridge:main#3b568a5f`), 2026-05-24.
**Lane**: agent-bridge (the ⑤ that #1011 punted as "另一条 lane").
**Status**: IN-PROGRESS.

## Question

Does the agent-bridge **Seed substrate** (used as a pluggable `EmbeddingBackend`,
SVD-projected) recall relevant memories better than the flat **ONNX** embedding
baseline that production currently uses?

This is the v22 substrate's core value claim, isolated. It is **orthogonal** to
the AiOT AutoResearch ① (cognitive-carrier readout): they tested
substrate-as-per-entity-carrier (MultiModalGrid) and falsified it at readout /
metric / policy levels (thread 31 #1016/#1017/#1023). agent-bridge uses the
substrate as an **embedding backend for recall** — a different application, so
the AiOT falsification does not transfer. Prior is still "probably no advantage".

## Why the decoupled form (not the original v22 P3)

v22 design (`DESIGN-v22-agent-bridge-memory-substrate.md`) already specs this as
**P1/P2/P3** with frozen thresholds (`MRR@10 ≥ 0.50`, `Recall@5 ≥ 60%`) and a
pre-registered **P6 null-path** (keep substrate as observability layer, DO NOT
wire into `memory_search` ranking). But P3 requires *14 days of continuous
substrate-live uptime* + `--use-substrate-bias`. Frame-audit found:
`substrate_stats: installed:false` — the live grid is **OFF** (`AB_SUBSTRATE=1`
unset), and the wrapper-clobber + reboots mean the 14d precondition was **never
met**. The substrate-recall hypothesis has therefore never been testable as
written. The decoupled probe answers the leading question now, mirroring the
AiOT lanes' frozen-grid approach.

## Method (gate-safe, decoupled)

`crates/bridge/examples/substrate_recall_eval.rs`. One arm per process
(`install_default` is a process-wide OnceLock). Small in-memory corpus
(N≥50 active non-skill memories); embed fresh under the arm's backend so the
cosine comparison is single-space:

- **query** = memory title (first meaningful content line)
- **document** = same memory's full content
- metric = **Recall@5** + **MRR@10** (+ Recall@1 secondary), leave-one-out over the corpus

Arms:
- **A = ONNX flat** — no `install_default` → `default_backend()` is raw ONNX (= current production recall path)
- **B = SeedBackend** — `ab_seed_bridge::install_default()` + `AB_SUBSTRATE_PROJECTION=svd`

## Falsifier (frozen — not to be moved post-hoc)

- `SUBSTRATE_HELPS_RECALL` — B Recall@5 ≥ A + 0.10 **and** B MRR@10 ≥ A + 0.05 → substrate adds real recall value → continue v22
- `NO_RECALL_ADVANTAGE` — B not meaningfully better than A → invoke v22 **P6 null-path** (substrate stays observability, not wired into ranking)
- `INDETERMINATE` — backend degenerate (hash fallback / dim 0) or ceiling (both ≈ 1.0 → corpus not discriminating; redo with harder set)

## Gate-safety

- Read-only over a **copy** of `state.db`; no DB writes; no live-store mutation.
- agent-bridge substrate ≠ AiOT iter-11 daemon (separate process / repo) → no daemon perturbation by construction.
- Light (≈100 embeds/arm), `nice`, and **no concurrent cargo build** (a sibling build holds the target lock — queue behind it).
- Willing to publish null/FAIL (project moat = honest negative verdicts).

## Result — `NO_RECALL_ADVANTAGE` (2026-05-24)

`crates/bridge/examples/substrate_recall_eval.rs`, leave-one-out over active
non-skill memories, query=title / doc=body-minus-title (v0 full-content design
ceilinged R@5=1.0 → INDETERMINATE → hardened per frozen falsifier).

| config | A=ONNX R@5 / MRR@10 | B=Substrate R@5 / MRR@10 | Δ R@5 / MRR |
|---|---|---|---|
| N=120, SVD | 0.675 / 0.529 | 0.650 / 0.496 | −0.025 / −0.033 |
| N=154 (req 200), SVD | 0.675 / 0.493 | 0.656 / 0.489 | −0.019 / −0.004 |
| N=120, no-SVD | 0.675 / 0.529 | 0.667 / 0.509 | −0.008 / −0.020 |

`embed_dim = 384` for both arms (SVD is a 384→latent→384 round-trip — adds loss,
not signal). Across all three configs the substrate backend is **statistically
indistinguishable from, and consistently slightly below, raw ONNX** — every Δ is
within ±0.03 and the SUBSTRATE_HELPS gate needed +0.10 (R@5) / +0.05 (MRR).

**VERDICT: `NO_RECALL_ADVANTAGE`** → invoke v22 **P6 null-path**: keep the Seed
substrate as an **observability / sensing** artifact; **do NOT wire it into
`memory_search` ranking** (would be optimizing against an unverified, here
falsified, target). Converges with AiOT ①/②/⑥ (substrate-as-cognitive-carrier
falsified) and P-α Day-7 (reinforce-active likely falsified): across recall,
carrier-readout, and reinforcement, the substrate adds no measured retrieval/
behavioral value — its honest niche is shared dynamical sensing, not per-memory
recall.

**Scope honesty**: this tests the substrate **embedding-transform** on a cold /
short-lived grid, not the v22-P3 *14d-learned attention bias* (still blocked on
uptime — substrate has never run 14d live). But the SVD artifact IS the "learned"
projection and shows no lift; combined with the AiOT convergence the 14d variant
is low-ROI to pursue. N=120–200, single corpus slice, deterministic Newest sort.

**Gate-safety honored**: read-only over a state.db copy; `substrate.parquet`
backed up + restored after each substrate-arm run (the arm flushes it); no AiOT
daemon touch.
