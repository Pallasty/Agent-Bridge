# AB internal regression benchmark (基尺)

Fixed, repeatable measurement harness so every ranking / rendering / weight
change can be judged by `diff` against a committed baseline instead of a
hand-rolled probe per arc. **Read-only**: it drives the deployed binary over
MCP stdio and opens `state.db` with `mode=ro`. It is deliberately a repo
script, not an MCP tool (30-day zero-call lanes taught us not to add tool
surface for producer-side instrumentation).

## Run

```bash
python3 scripts/eval/ab_eval.py                       # run all, write baselines/<date>.json
python3 scripts/eval/ab_eval.py --compare scripts/eval/baselines/2026-07-06.json
python3 scripts/eval/ab_eval.py --component retrieval  # one component only
```

Default binary: `~/.local/bin/agent-bridge` (the wrapper, so machine.env is
sourced and the embedder works). Override with `--binary`.

## Components

1. **retrieval** — replays curated real `(query → expected key)` pairs from
   `fixtures/retrieval_pairs.json` through `memory_search` in fts / hybrid /
   semantic modes; reports hit@5, hit@10, MRR per mode and per pair.
   Labels come from `retrieval_surfacing` rows with `used_at` set.
   **Known limitation**: `used_at` conflates task-use with governance reads
   (a forensic `memory_get` during curation stamps it too — observed
   2026-07-06); pairs are therefore hand-curated, never bulk-imported.
2. **continuity** — runs `session_bootstrap` and checks the restore-drill
   checklist (`fixtures/continuity_checklist.json`): T1 hard constraints and
   T2 conventions must surface (as full rows, index lines — floor lines from
   PR#75/#76 — or profile text); T3 probes are informational (ephemeral state
   rotates). This is drill #1 (2026-07-06) mechanized.
3. **distillation** — active since 2026-07-07 (corpus gate ≥10 pub_* rows
   met at 11). Scores the S1 candidate detector against the hand-curated
   corpus: ground truth = the pub_* rows' non-pub provenance links, recall
   on the in-store subset (file-archive provenance is invisible to a
   store-side detector by construction — those lessons reach pub_* through
   the session double-write convention instead). Also reports detector
   population (propose-only queue size). Detector heuristic: verified
   lessons/error_patterns (`continuity_confidence:verified`) + verified
   outcomes (`verify:verified` facet — different tag vocabulary, both
   required), excluding zone:public and `distill:no`-dismissed rows.
   Informational — does not gate the compare verdict. Falls back to gated
   below 10 corpus rows.
4. **governance lint** — read-only sweep for suspicious stale high-privilege
   rows: `must_block` + `version_bound`/`project_phase_bound` freshness +
   older than 14 days. `freshness_policy` is declarative with no runtime
   enforcement; this lint is its minimal enforcement form. Output is a
   report — disposition stays a curation decision.

   **v1 role split**: rows tagged `continuity_role:constraint` are
   conditional gates — they block an action until its gates are satisfied,
   and age alone does not expire them (adjudications 2026-07-05/06 both
   kept flagged constraint rows). They are excluded from `suspects` and
   surface in `aging_constraints` only past 45 days, framed as periodic
   review, not staleness. All other roles (`state`, `procedure`, `warning`,
   …) keep the 14-day suspect threshold.

## Sibling probes (not benchmark components)

`ambient_gate.py` — ambient stage-2 data-gate probe (OPEN/WAIT): is the
mode=bootstrap telemetry slice ripe enough to calibrate an ambient-specific
reinforce rule? Maturation gate for a parked lane, not a regression component;
it never touches baselines. Run: `python3 scripts/eval/ambient_gate.py`.

`portfolio_continuity_eval.py` — deterministic, no-write scorer for redacted
portfolio/session digest evidence packets. It measures required supported-claim
coverage, current evidence precision, stale/unknown evidence, forbidden or
unsupported claims, correct abstention, token cost, and latency. Claim ids are
review labels supplied by an upstream adapter or reviewer. This scorer is not a
natural-language judge.
Candidate objects use strict field whitelists, bounded claim/evidence labels,
unique JSON fields, and finite numeric diagnostics. It does not call retrieval,
an LLM, or the AB store.
It is contract-only and does not enter the daily baseline yet. Run:

```bash
python3 scripts/eval/portfolio_continuity_eval.py \
  --fixture scripts/eval/fixtures/portfolio_continuity_contract.json \
  --candidate scripts/eval/fixtures/portfolio_continuity_candidate_pass.json \
  --strict
```

## Baselines

First baseline per day is written to `baselines/<date>.json`; commit it with
the change that motivated the run. The compare baseline is loaded **before**
this run writes its own file, so same-day compares diff against the committed
state, not against themselves (v1 fix — the original ordering made every
same-day compare a trivial +0.000 PASS).

Baselines are **full-run snapshots**: a `--component` run never writes the
default baseline path (pass `--out` explicitly to save one) — a partial file
there blinds the next day's `--compare` (v1.1 fix, bit us 2026-07-07 when a
`--component lint` run clobbered the day's full baseline).

Only **any_mode** MRR gates the verdict. Single modes breathe on a living
corpus (measured 2026-07-06: hybrid ±0.06 on an unchanged DB as the
coactivation graph moves; one near-tie fts rank flip per ~10-row write day
= 0.056 MRR swing on 9 pairs). Per-mode deltas print as informational
notes. Pairs whose query legitimately matches several rows list them in
`expected_any` (best rank counts) — label the adjudication in a `note`.
`--compare` prints per-metric deltas and
a PASS/REGRESS verdict (any_mode MRR drop > eps or any required continuity
probe lost ⇒ REGRESS).

## Fixture update discipline

- `continuity_checklist.json` changes ride the same PR as the convention
  change that motivates them (T1/T2 lists are versioned facts, not config).
- `retrieval_pairs.json`: only add pairs you can defend as genuine task-use;
  record excluded-as-noise pairs in the `excluded` section with a reason.
- Budget/token lessons: measure with CJK corpora — ASCII corpora underestimate
  line cost ~2.5× (PR#76 lesson).
