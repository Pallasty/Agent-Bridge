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
3. **distillation** — GATED, not implemented: corpus < 10 pub_* rows gives
   nothing to evaluate honestly. Unlock with P1 corpus growth.
4. **governance lint** — read-only sweep for suspicious stale high-privilege
   rows: `must_block` + `version_bound`/`project_phase_bound` freshness +
   older than 14 days. `freshness_policy` is declarative with no runtime
   enforcement; this lint is its minimal enforcement form. Output is a
   report — disposition stays a curation decision.

## Baselines

First baseline per day is written to `baselines/<date>.json`; commit it with
the change that motivated the run. `--compare` prints per-metric deltas and
a PASS/REGRESS verdict (retrieval MRR drop > 0.05 or any required continuity
probe lost ⇒ REGRESS).

## Fixture update discipline

- `continuity_checklist.json` changes ride the same PR as the convention
  change that motivates them (T1/T2 lists are versioned facts, not config).
- `retrieval_pairs.json`: only add pairs you can defend as genuine task-use;
  record excluded-as-noise pairs in the `excluded` section with a reason.
- Budget/token lessons: measure with CJK corpora — ASCII corpora underestimate
  line cost ~2.5× (PR#76 lesson).
