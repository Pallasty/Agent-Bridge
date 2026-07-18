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
sourced and the embedder works). Override with `--binary`. The harness always
overrides `AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS=eval`, so benchmark searches
and bootstrap calls cannot be counted as organic telemetry.

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

`engram_g0_failure_intake.py` — live-store-read-only G0 intake and baseline replay for a
consumer-owned precision/generalization failure. Real private specs stay under
ignored `data/`; capture runs FTS/hybrid/semantic searches only against a
fresh disposable clone of one frozen SQLite backup per probe/mode observation,
with the BioCortex retrieval path forced off. A hash-only environment receipt
binds retrieval knobs and embedding transport, and any active perception-filter
rerank state is copied once and frozen across observations. The
redacted receipt distinguishes generalization gaps, overgeneralization gaps,
ordinary retrieval misses, and no-gap cases. Even a positive real receipt only
opens G1 grouped-corpus design; it grants no candidate, ranking, memory-write,
corpus-freeze, or runtime authority. See
`docs/design/ENGRAM_G0_REAL_FAILURE_INTAKE_2026_07_17.md` and run
`scripts/check-engram-g0-failure-intake.sh`.

`engram_g1_corpus_design.py` validates the aggregate-only G1 grouped-corpus
preregistration opened by a positive real G0 receipt. It fixes episode-level
FIT/development/sealed splits, provenance and role separation, a specificity
primary endpoint, exact/related non-inferiority guards, matched-arm names, and
a bounded observation budget. It rejects raw probes, keys, split membership,
threshold relaxation, or any later-stage authority. A passing receipt permits
only independent consumer corpus-assembly review; it does not freeze a corpus
or authorize candidate code, retrieval mutation, BioCortex execution, or
runtime promotion. See
`docs/design/ENGRAM_G1_GROUPED_CORPUS_PREREGISTRATION_2026_07_17.md` and run
`scripts/check-engram-g1-corpus-design.sh`.

`engram_g1_freeze_preflight.py` is the G1.1 successor boundary. It preserves
the G1 v0 bytes while replacing sample-size-dependent rate interpretation with
paired integer gates, separating the Agent-Bridge failure-classification
baseline from the later stable/density experiment comparators, and fixing the
30-group family cap at 10. It validates hash-only private role and grouped-
corpus packets, but does not authenticate identities or receipts. Real packets
must remain untracked under ignored `data/`; redacted receipts contain only
aggregate counts. Contract, role, and manifest passes grant review readiness
only—never corpus assembly/freeze, candidate implementation, BioCortex
execution, retrieval mutation, live writes, or promotion. See
`docs/design/ENGRAM_G1_FREEZE_PREFLIGHT_2026_07_18.md` and run
`scripts/check-engram-g1-freeze-preflight.sh`.

`engram_g1_role_review.py` is the G1.2 appointment-review boundary. It binds
the exact G1.1 role-packet bytes to separate application-owner and outside-
auditor reviews, then binds a later owner endorsement to the completed review.
The owner may equal only the consumer curator; the auditor must be outside all
five role holders. Synthetic and claimed-real chains always emit zero
authority. A claimed-real chain must stay untracked under ignored `data/` and
can only propose curator-run private intake, read-only disposable-snapshot
replay, and a hash-only manifest capped at 36 groups for later authenticated
authority review. It cannot open intake, freeze a corpus, authorize candidate
code or candidate-lane assembly, execute BioCortex, mutate retrieval, write
live state, or promote runtime. Review and decision packet identifiers are
opaque SHA-256 values, cannot alias any private commitment or receipt in their
packet lineage, and are omitted from redacted receipts, preventing those
receipts from echoing identity-like labels. The validator checks packet structure and commitments, not real
identities, evidence truth, or signatures. See
`docs/design/ENGRAM_G1_ROLE_APPOINTMENT_REVIEW_2026_07_18.md` and run
`scripts/check-engram-g1-role-review.sh`.

`ambient_gate.py` — ambient stage-2 data-gate probe: is the explicitly organic
`mode=bootstrap` telemetry slice ripe enough to calibrate an ambient-specific
reinforce rule? Eval and historical unknown rows are excluded. A missing class
column, no labelled organic data, or unknown/invalid rows after organic
collection begins produce distinct fail-closed verdicts; only clean organic
traffic can reach OPEN. This is a maturation gate for a parked lane, not a
regression component, and it never touches baselines. Run:
`python3 scripts/eval/ambient_gate.py`.

`temporal_truth_drift_audit.py` — aggregate-only structural audit for explicit
stale-active evidence: lifecycle status/edges, declared supersession,
correction-edge coverage, bounded-freshness age, and active dedupe conflicts.
It does not read memory prose or assert semantic truth, emits no keys, and has
no retirement authority.

`retrieval_telemetry_causality_audit.py` — fail-closed observability gate for
separating organic and eval retrieval telemetry before surfaced-to-used
reinforce/decay evidence is interpreted. It never reads query text or infers
traffic from keys/timing. Missing or partial `traffic_class` labels block; even
complete labels admit only a separately frozen clean shadow, never apply.
Its sibling ambient section uses the same organic-only and post-label-unknown
rules as `ambient_gate.py`.

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

`portfolio_continuity_ab_trial.py` builds the private AB-native capture and
review input for that scorer. Its `capture` command opens the source SQLite
database read-only, makes an online backup, and launches Agent-Bridge with
`AGENT_BRIDGE_DB` pointing at the temporary snapshot. It fails unless child
stderr confirms that exact snapshot path. The source DB path is never passed
to the child.

The workflow has four explicit stages:

```bash
python3 scripts/eval/portfolio_continuity_ab_trial.py capture ...
python3 scripts/eval/portfolio_continuity_ab_trial.py review-template ...
python3 scripts/eval/portfolio_continuity_ab_trial.py apply-review ...
python3 scripts/eval/portfolio_continuity_ab_trial.py assemble ...
```

Review decisions use the v1 schema. `apply-review` verifies their binding to the
exact capture bytes, review-template bytes, and selector/content manifest;
the template must also exactly match the capture-derived review structure.
Legacy or mismatched inputs fail closed. `review-template` and `apply-review`
write their private packets to the requested files and print only a schema/hash
receipt to stdout. `assemble` requires the same template and decisions,
re-derives the final review, and rejects any semantic drift before it writes
scorer packets.

Real in-repo raw captures are accepted only below `data/` after `git
check-ignore` confirms the path and `git ls-files` confirms it is untracked;
output paths may not alias the capture spec, source DB, or Agent-Bridge binary.
Capture outputs keep their resolved destination directories open across
collection; containment, ignore, and tracking checks use those fixed paths, and
JSON leaves are created/replaced through the same descriptors. Existing
same-inode aliases fail closed. Repository fixtures are synthetic. The redacted
capture and assembly summary contain hashes, labels, counts, timing, and token
estimates only. The adapter does not call an LLM and does not claim answer
quality or runtime promotion. It uses `subprocess` environment maps directly;
do not wrap it with bare `env`, because this host may have a user-level `env`
shim ahead of `/usr/bin/env`.

`portfolio_continuity_answer_trial.py` is the separate owner-blinded answer
gate. Its checked-in contract fixes four conditions before collection: full
hybrid search, S4 compact search followed by `memory_get` for exactly the first
two unique ranked keys, session bootstrap, and direct digest. Capture clones
one read-only online backup into a fresh SQLite file for every case/condition,
requires every child to confirm its copy, and fails if compact projection
changes ranking or leaks a full record.

Generation invokes the preregistered Codex CLI/model once per answer in an
empty ephemeral read-only directory. User config and project rules are ignored,
tool-call events fail the run, and the same instruction limits answers to the
captured evidence. A committed seed hash binds the private randomization; the
owner packet has opaque answer ids and no condition mapping. The separate map
can be consumed only with a complete, hash-matching owner review. The score
command validates that review before it opens either the condition-labeled raw
generation packet or the blind map:

```bash
python3 scripts/eval/portfolio_continuity_answer_trial.py validate-contract \
  --contract scripts/eval/fixtures/portfolio_continuity_answer_contract.json
python3 scripts/eval/portfolio_continuity_answer_trial.py capture ...
python3 scripts/eval/portfolio_continuity_answer_trial.py generate ...
python3 scripts/eval/portfolio_continuity_answer_trial.py score ...
```

Contract v1 narrows the expanded gate to full hybrid versus direct digest over
12 frozen prompts in six strata. It binds the exact harness, retrieval-surface
helper, and digest-key identities, requires two distinct independently
completed blind reviews, and applies the same
absolute/non-inferiority/efficiency gate separately to every reviewer and
stratum. Supply both private reviews by repeating the argument:

```bash
python3 scripts/eval/portfolio_continuity_answer_trial.py score ... \
  --review data/eval/<trial>/review.1.json \
  --review data/eval/<trial>/review.2.json
```

The checked-in v1 fixture is historical and source-bound to contract commit
`f472244f`; run it only from that exact worktree. The verifier audits its bytes
and source commitments at the frozen commit, while synthetic v1 coverage binds
and exercises the current harness. V1 refuses capture/generation unless its
contract, harness, and surface-helper bytes are tracked at the spec's exact
commit. Capture validates its canonical raw payload before writing either
output. V1 preserves zero- or one-hit full hybrid results as observed retrieval
outcomes; only v0's compact top-2 projection requires at least two unique
full-search hits. It validates both complete reviews before opening the
condition-labelled generation packet or blind map. Even a full pass can only
recommend preregistering a separate write-side digest trial.

Contract v2 is the preregistered successor protocol. Each private case freezes
a separate retrieval query in addition to the original question. Capture keeps
the raw MCP result private, but model context is a deterministic projection
that drops record keys and replaces fixed internal identifiers with readable
aliases. Non-abstention reference cases require at least two unique hits;
abstention cases may have zero. Generation stops before model invocation unless
the capture coverage status is `VALID`.

V2 requires a fresh ignored failure path. A classified failure writes an atomic
private receipt containing hashes and failure coordinates, never raw prompts,
queries, contexts, answers, or markers. There is no automatic retry. Only a
first-attempt pre-model infrastructure receipt can authorize one explicit full
restart. Every v2 capture binds the exact private-spec byte hash; generation
rejects a spec/capture mismatch before it can claim or invoke a model.
Single-use attempt claims are scoped to the frozen public contract, so changing
spec formatting or recapturing cannot create another attempt 1; they retain
spec/capture hashes for provenance and also prevent attempt-2 receipt replay.
The v2 contract also commits the canonical execution-worktree path hash, so an
alternate worktree or clone fails before capture can create a separate local
claim directory. This is a managed-host guard, not a tamper-proof cross-host
ledger. Any model-started, tool, schema, marker, or other semantic failure has
zero retries. Answers are stored and blinded exactly as returned; v2 applies no
output postprocessing.

```bash
python3 scripts/eval/portfolio_continuity_answer_trial.py validate-contract \
  --contract scripts/eval/fixtures/portfolio_continuity_successor_answer_contract.json
python3 scripts/eval/portfolio_continuity_answer_trial.py generate ... \
  --failure-output data/eval/<trial>/generation.failure.json
# Only when the first receipt explicitly authorizes a restart:
python3 scripts/eval/portfolio_continuity_answer_trial.py generate ... \
  --failure-output data/eval/<trial>/generation.retry.failure.json \
  --prior-failure-receipt data/eval/<trial>/generation.failure.json
```

Prompts, v2 retrieval queries, contexts, answers, seed, condition map, receipts,
retry claims, and private reviews must remain under ignored `data/`. The v0
score can recommend only an expanded answer trial; v1/v2 can recommend only
preregistration of a separate write-side trial. None is authority for digest
regeneration, a compact default, retrieval/runtime changes, benchmark claims,
versioning, tagging, or release.

Contract v3 is isolated in `portfolio_continuity_successor_v3_trial.py`; the
source-bound v2 harness remains unchanged. V3 retains the v2 corpus,
generation, coverage, projection, and all-gates score but uses a fresh
execution and blind identity. It replaces free-form reviewer identities with
two fixed headless-model slots: Claude `claude-opus-4-8` and Codex
`gpt-5.6-sol` at max effort. Gemini is forbidden. The OpenAI review slot's
provider overlap with the `gpt-5.4` generator and the scheduler's corpus COI
are explicit contract fields.

Each v3 score requires two private review packets, custodian receipts, full
strict parsed command records, and structured model responses byte-identical
to the review packets. Their CLI/model/effort argv, command, deterministic request, response/review,
workspace, no-tool/no-MCP, and COI hashes are validated before
condition-labelled generation or map bytes are opened. A
single-use score claim is created immediately before unblinding. V3 also makes
forbidden-claim labels opaque in the blind packet and reports cross-provider
agreement only as a diagnostic; reviewer results are never pooled for gates.

```bash
python3 scripts/eval/portfolio_continuity_successor_v3_trial.py \
  validate-contract \
  --contract scripts/eval/fixtures/portfolio_continuity_successor_v3_answer_contract.json
python3 scripts/eval/portfolio_continuity_successor_v3_trial.py score ... \
  --review data/eval/<trial>/review.anthropic.json \
  --review data/eval/<trial>/review.openai.json \
  --review-receipt data/eval/<trial>/receipt.anthropic.json \
  --review-receipt data/eval/<trial>/receipt.openai.json \
  --review-command data/eval/<trial>/command.anthropic.json \
  --review-command data/eval/<trial>/command.openai.json \
  --review-response data/eval/<trial>/response.anthropic.json \
  --review-response data/eval/<trial>/response.openai.json
```

The score claim is not an operator argument. V3 derives one fixed private
claim path from the frozen contract hash before unblinding, so changing the
score output path cannot create another allowance.

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

## Verdict validity: positive-control hard rule

Adopted 2026-07-14 from the AiOT memory-value measurement program (forum
thread 102 post #3124, AB triage #3125). AiOT's A2 audit caught a saturated
success criterion only because an ORACLE arm — the true answer seeded
directly into context — showed no difference either, proving the instrument
rather than the memory was broken (their production criteria measured
FPR 0.57–0.72).

**The rule**: a verdict from a new or modified instrument (benchmark
component, promotion gate, shadow trial, relevance-lift eval) is valid only
if the instrument has demonstrated it can detect a known positive under the
same conditions — a gold row seeded into the measured surface, a sentinel
write asserted visible where it must be (and absent where it must not), or
an existing gold fixture the instrument is expected to hit. Positive
control not detected ⇒ **verdict INVALID**, and the failure is presumed to
be the instrument's until shown otherwise (自研仪器先怀疑仪器 — eval v1,
2026-07-06).

Existing practice already in this shape (keep doing it): `digest_gate.py`'s
isolation sentinel (write a row, assert it appears in the shadow copy and
NOT in the live store, abort otherwise) and its hit gate (the candidate
digest must itself rank ≤5 on its target queries). Local precedent for why
the rule pays: the 2026-07-13 digest_gate first-run FAIL that per-query
diff instrumentation exposed as a draft-row artifact, not a regression.

## Fixture update discipline

- `continuity_checklist.json` changes ride the same PR as the convention
  change that motivates them (T1/T2 lists are versioned facts, not config).
- `retrieval_pairs.json`: only add pairs you can defend as genuine task-use;
  record excluded-as-noise pairs in the `excluded` section with a reason.
- Budget/token lessons: measure with CJK corpora — ASCII corpora underestimate
  line cost ~2.5× (PR#76 lesson).
