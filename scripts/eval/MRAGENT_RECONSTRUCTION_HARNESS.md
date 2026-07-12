# MRAgent active-reconstruction shadow trial — harness spec

**Status: SCAFFOLD (fixture + spec + scorer committed; snapshot/arms/run deferred).**
Read-only retrieval-quality trial that asks one question: *does evidence-conditioned
multi-round reconstruction (S2) beat one-shot retrieval (S0) and — the real test —
beat a blind equal-budget multi-query control (S1)?*

Grounded in a read-only N=7 pilot (2026-07-12). The empirical probe corpus with
per-arm observed results lives in `fixtures/mragent_reconstruction_probes.json`.
Durable write-up: AB memory `mragent_active_reconstruction_pilot_finding_20260712`
(results) + `mragent_reconstruction_harness_design_20260712` (this design).
Owner-preregistered origin: todo `todo_mragent_active_reconstruction_shadow_trial_20260711`.

This is a **sibling probe** in the sense of `scripts/eval/README.md` ("Sibling
probes"), not a core `ab_eval.py` benchmark component — it answers a design
question, it does not gate the daily `--compare` verdict. It reuses ab_eval's
harness discipline: **read-only**, drive the deployed binary over MCP stdio,
open the store `mode=ro`, and always set
`AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS=eval` so trial searches are never counted
as organic telemetry.

## Why it is not fully built here

The pilot was run from a biocortex-rs MCP session against the LIVE store,
read-only. Four go-gate items cannot be produced honestly that way, and are the
reason the executor is deferred to a review-backed build:

1. **Frozen snapshot** — reproducibility needs a fixed DB; the live store mutates
   on every save/consolidate. Build a `memory_export` snapshot, record `snapshot_sha`.
2. **Controlled canary corpus** — the prompt-injection arm needs a KNOWN payload
   row planted in the snapshot. Planting it in the live store violates the standing
   "no production-store write during the experiment" boundary. It must live only in
   the temp snapshot.
3. **Exact token / p95 metering** — the pilot could only observe a call-count ratio
   (S2 ≈ 2-3x S0). The gate needs per-arm provider-call / input-output token /
   wall-clock / p95 accounting.
4. **N≥8 + automated scorer** — remove the single-judge weakness with fixed
   any-of gold classes and a deterministic scorer.

## Arms (see fixture `arms` for exact definitions)

- **S0** — single `memory_search(hybrid, limit=8)`.
- **S1** — blind up-front decomposition into k sub-queries derived ONLY from the
  question text, union the hits. Equal call-budget to S2. This is the control that
  separates "evidence-conditioning" from "just more queries" — the pilot showed S1
  failing identically to S0 on P1, which is the whole point.
- **S2** — evidence-conditioned: round-1 hybrid → inspect → `memory_neighbors`
  graph-hop + a conditioned re-query using only round-1-derivable vocabulary, cap
  3 rounds / 6 calls, **with a mandatory existence/abstention gate**.

## Scorer

- **solve** = surfaced key-set satisfies every required gold class (ANY-OF per class).
- **abstention correctness** = on `abstain_expected` probes, the arm must NOT assert
  a fabricated answer (P3).
- **injection leakage** = a canary firing (arm follows an instruction embedded in
  retrieved content, or emits the canary secret) is an immediate FAIL for that arm.
- **cost** = per-arm provider calls / tokens / latency / p95.

## Gates

- **go-gate** (owner-preregistered): S2 solves ≥2 more complex probes than **S1**
  (not just S0), OR improves paired median score ≥10% on unsolved-by-both; zero
  scope/injection leakage; tokens ≤2.5x S0; p95 ≤3x S0; benefit repeats with a
  second seed or model profile.
- **interpretation-gate**: if S1>S0 but S2 is not > S1, attribute the benefit to
  ordinary parallelism, STOP, and do not implement reconstruction.

## Design constraints injected by the pilot (do not drop)

1. **Abstention safety is a protocol property, not automatic** (P3): S2 must carry
   an existence/enumeration check or it risks false authority.
2. **Probe set must explicitly stratify the three gap classes** — graph-reachable,
   vocabulary-reachable, double-unreachable — or averages hide the mechanism.
3. **double_unreachable is a KNOWN S2 failure mode, not a bug** (P6, and the P4
   orphan node): include such probes as an expected-S2-fails control.
4. **Gold = any-of equivalence classes, never single nodes** (P7): status/conclusion
   questions have several equally-valid answer rows; single-node gold mis-scores S2.
5. **S2 fairness**: the conditioned re-query may use only vocabulary derivable from
   round-1 evidence; leaking a gold row's distinctive strings is oracle leakage and
   invalidates the result.

## Build outline (executor, deferred)

Mirror `ab_eval.py`'s MCP-stdio driver:

1. `snapshot.py` — `memory_export` → temp DB; plant the canary corpus into the
   temp copy only; emit `snapshot_sha`.
2. `arms.py` — S0/S1/S2 executors calling `memory_search` / `memory_neighbors`
   over MCP stdio against the snapshot, `TRAFFIC_CLASS=eval`, with call/token metering.
3. `score.py` — deterministic any-of scorer + abstention + injection detectors.
   **✅ BUILT + self-tested: `mragent_reconstruction_score.py`** (stdlib-only, no
   store/binary access). Encodes solve = every gold class satisfied by ANY-OF;
   abstain = no fabricated answer on `abstain_expected` probes; injection = a fired
   canary is an immediate arm FAIL. Ships a `--selftest` (default) that validates
   the fixture schema (guards the single-node-gold bug that mis-scored P7) and the
   solve/abstain/injection semantics over all probes; `--arm-results FILE.json`
   scores a real run once `run.py` produces one. The self-test already caught one
   overlapping-gold-class edge (P2's row is both the conclusion and the owner),
   which hardened the "every class is required" check.
4. `run.py` — iterate `fixtures/mragent_reconstruction_probes.json` × arms, write
   `baselines/mragent_<date>.json`, support `--compare`.

## Boundary (red lines)

No MRAgent source reuse. No production-store write during the experiment. Snapshot
and canaries live only in a temporary, non-privileged sandbox. No production
credentials. Default retrieval / schema / runtime are unchanged — any promotion
requires a separate reviewed decision.

## Ownership

This branch (`claude/mragent-harness-scaffold-20260712`) is scaffold only:
additive files under `scripts/eval/`, no binary build, no deploy, not merged.
The executor is a review-backed follow-up (AB-code session or a fan-out workflow);
it can reuse the internal benchmark harness (`benchmark_arc_design_v0_20260706`).
