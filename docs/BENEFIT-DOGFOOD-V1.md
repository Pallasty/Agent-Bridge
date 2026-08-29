# Agent-Bridge benefit dogfood V1

Status: source-only collection instrument. Source-side path selection is
fail-closed and the remaining evidence-admissibility rules are documented;
live authorization and the operator-enforced window remain pending. There is
no daemon integration, scheduler, service, Avatar launch, voice enablement,
action authority, deployment, or runtime influence.

## Decision

The next Agent-Bridge stage is a two-week real-workflow value trial. It asks
whether the already shipped continuity and embodiment surfaces reduce owner
coordination cost without adding distraction, duplicated external actions, or
new authority. It does not ask whether another model, renderer, protocol, or
memory ranker can be built.

## Collection start gate

The collection start gate is separate from all four value gates. It authorizes
only manual recording of newly occurring real workflows inside the frozen
boundaries below. Passing source tests, reading an empty report, or creating an
empty file does not create a sample and does not make an adoption claim.

A formal trial must satisfy all of these conditions before its first event:

- the owner explicitly authorizes live collection at `authorization_at` and
  chooses one canonical writer node; kickoff evidence binds that authorization,
  a salted node digest, and the unique ledger path or digest before only that
  node may invoke `record-*`;
- every command names the same new, initially absent, absolute
  `--log` path;
- only observations or sessions that begin after `authorization_at` are
  eligible; both legs of an embodied pair must begin after authorization, and
  historical receipts, outcome rows, and memories are never backfilled;
- the first accepted eligible row establishes `starts_at`; `ends_at` is exactly
  `starts_at + 1209600` seconds. V1 records reduction time in `observed_at` and
  cannot independently prove producer freshness or enforce the window, so both
  remain explicit operator checks and the window never auto-extends;
- at `ends_at`, recording stops and later rows are inadmissible. If the locked
  minima are incomplete, the result is insufficient evidence rather than a
  value verdict; any extension or replacement trial needs fresh owner
  authorization and a new ledger;
- an eligible continuity task genuinely resumes work across a model, process,
  or session boundary; an Avatar event is one owner-started foreground session
  rated after use; an embodied event is one pre-paired baseline/trial task; and
  a voice event is one explicit Qwen session with owner audible confirmation;
- a harmful recall, duplicate external action, or embodied safety failure stops
  collection for review immediately.

The source start gate therefore closes implicit path-selection ambiguity and
documents the operator-enforced admission contract. It does not mechanically
prove authorization, producer freshness, writer identity, or window timing.
The live kickoff, first real event, complete evidence minima, and owner adoption
review remain distinct later gates.

`--attest-real-task` attests one event at record time. It is not owner live-
collection authorization and cannot substitute for the separate kickoff
evidence above.

`scripts/agent-bridge-benefit-dogfood.py` stores four kinds of content-free
events in one owner-local JSONL ledger:

- `continuity`: eligible resumed task, recall outcome, owner restatements,
  completion, and optional recovery time;
- `avatar`: a reduced EAP-1C Linux live receipt plus one owner rating;
- `embodied`: paired baseline/trial burden counts for one real task;
- `voice`: reduced Qwen adapter invocation counts, session-average latency,
  warm/cold state, and owner audible confirmation.

Unknown fields are rejected. Task text, prompts, transcripts, memory keys,
Avatar session IDs, sidecar transition bodies, and receipt bodies have no place
in the event schema.

## Locked decision metrics

| Gate | Minimum evidence | Pass threshold | Guardrail |
|---|---:|---|---|
| continuity | 20 resumed real tasks | no-restatement success rate >= 80% | harmful recall = 0 |
| Avatar | 20 rated foreground sessions | helpful >= 60%; distracting <= 10% | operational failure sessions = 0 |
| embodied | at least 2 hashed task domains | paired total burden reduction >= 30% | no per-event regression, duplicate action, safety failure, or cleanup failure |
| voice | at least 2 warm sessions | session-average invocation p50 <= 2 s and p95 <= 5 s | failures = 0; every warm sample audibly confirmed |

One continuity success means the task completed with zero owner restatements and
the recall outcome was neither `stale` nor `harmful`. `no_recall` and `missing`
remain separately visible outcomes; they count as a no-restatement success only
when the task still completed without owner restatement.

The burden numerator is the sum of owner restatements, manual interventions,
and agent-visible orchestration calls. Its denominator is the paired baseline
sum over the same fields. This is an operator-burden proxy, not a causal claim.

The current Linux live receipt exposes whole adapter-invocation duration, not
time to first playable sample. V1 therefore uses session-average invocation
duration as a conservative interaction-latency proxy and reports cold sessions
separately. It must not be relabeled as model-only inference latency.

`physical_display_confirmed` is retained as supporting owner evidence but is
not a separate V1 pass condition. The locked Avatar gate uses the post-session
owner rating plus the receipt's completion, heartbeat, and sidecar-read fields.

The reducer returns:

- `COLLECTING_TWO_WEEK_DOGFOOD` while any evidence minimum is unmet;
- `STOP_AND_REVIEW` immediately for harmful recall, duplicated external action,
  or an embodied safety failure;
- `READY_FOR_OWNER_ADOPTION_REVIEW` only when all four gates pass;
- `RETAIN_ON_DEMAND` when the sample is complete but one or more value gates
  fail.

No verdict changes runtime behavior. Even a fully passing report requires a
separate owner adoption decision.

## Relationship to the general task-outcome ledger

This Python/JSONL ledger remains the locked decision instrument for the four
V1 adoption gates above. Its event schemas, sample minima, reducer thresholds,
stop conditions, and content-free export are not changed by the general
`agent_task_outcomes` SQLite ledger.

The general ledger receives an optional explicit result through
`session_finalize` and lets `practical_workflow_scorecard` report task status,
verification, rollback disposition, and per-field operator-burden claims
without inferring them from lifecycle calls. The public producer is
agent-reported only: it cannot assert authenticated owner/harness provenance,
and owner acceptance remains unknown. Missing burden fields remain unavailable
rather than becoming zero. It is an operational claim source, not an input to
this locked four-gate reducer. It does not backfill dogfood samples, translate
one event type into another, or make an adoption decision.

The evidence authorities therefore remain separate:

- this owner-local JSONL ledger decides only the locked continuity, Avatar,
  embodied, and voice trial;
- the SQLite outcome ledger supports general explicit workflow outcomes;
- Tool Atlas and MCP dispatch audit own tool usage, failure, latency, and
  payload evidence; and
- the dedicated body-operation receipt ledger stores redacted, advisory public
  receipts atomically without executing or authorizing an action; caller
  claims are not promoted to verified Event Spine verdicts.

Representing the same real workflow in two ledgers requires two explicit
records satisfying the respective schemas. No automatic copy or double count
is allowed, and neither ledger overrides the other's decision boundary.

## Local ledger

Formal R4 collection never guesses a platform-specific ledger. Every formal
trial command must receive the same explicit absolute `--log` path. When
`--log` is omitted for an ad hoc diagnostic only, the script may inherit an
absolute `AGENT_BRIDGE_STATE_DIR` and resolves:

```text
$AGENT_BRIDGE_STATE_DIR/dogfood/benefit-v1.jsonl
```

The script deliberately does not source the installed wrapper's `machine.env`
and does not fall back to `XDG_STATE_HOME`, `~/.local/state`, or macOS
`Application Support`. This prevents a direct Python invocation and a
wrapper-launched process from silently writing different ledgers. Bind one
unique absolute path in the kickoff evidence and set
`BENEFIT_DOGFOOD_LEDGER` to that exact value out of band; the examples below
assume it is already set.

If a legacy candidate is discovered later, stop and reconcile it explicitly.
Do not automatically fall back, merge, move, or delete ledger files.

An empty `report` against an absent path proves resolution and zero-write
behavior only. It does not prove that the parent is private, writable, or
durable. The first eligible event remains the write-side gate and must verify
the resulting directory mode `0700`, file mode `0600`, and persisted row.

The directory is mode `0700`; the append-only file is mode `0600`, opened with
`O_NOFOLLOW`, file-locked, bounded to 16 MB, and rolled back to its prior length
after a failed append. Duplicate event IDs and duplicate `(event type, subject
digest)` identities are rejected.

Use a private salted SHA-256 reference for manual task subjects and domains.
Only the digest enters the ledger. Do not place a project name, task title,
prompt, path, host name, or other content in a digest field.

## Recording examples

Record one resumed task:

```bash
python3 scripts/agent-bridge-benefit-dogfood.py \
  --log "$BENEFIT_DOGFOOD_LEDGER" \
  record-continuity \
  --attest-real-task \
  --subject-sha256 sha256:<private-salted-task-digest> \
  --recall-outcome used \
  --owner-restatements 0 \
  --task-completed \
  --recovery-seconds 45
```

Reduce an existing foreground `avatar linux-live --json` receipt. The receipt
itself remains outside the ledger:

```bash
python3 scripts/agent-bridge-benefit-dogfood.py \
  --log "$BENEFIT_DOGFOOD_LEDGER" \
  record-avatar \
  --attest-real-task \
  --receipt /private/path/linux-live-receipt.json \
  --owner-rating helpful \
  --physical-display-confirmed
```

Record the voice portion of a receipt separately so the same underlying receipt
can contribute to both Avatar and voice gates without duplicating either event
type:

```bash
python3 scripts/agent-bridge-benefit-dogfood.py \
  --log "$BENEFIT_DOGFOOD_LEDGER" \
  record-voice \
  --attest-real-task \
  --receipt /private/path/linux-live-voice-receipt.json \
  --worker-state warm \
  --audible-confirmed
```

Record one paired embodied task:

```bash
python3 scripts/agent-bridge-benefit-dogfood.py \
  --log "$BENEFIT_DOGFOOD_LEDGER" \
  record-embodied \
  --attest-real-task \
  --subject-sha256 sha256:<private-salted-task-digest> \
  --domain-sha256 sha256:<private-salted-domain-digest> \
  --baseline-owner-restatements 1 --trial-owner-restatements 0 \
  --baseline-manual-interventions 1 --trial-manual-interventions 0 \
  --baseline-agent-calls 7 --trial-agent-calls 2 \
  --duplicate-actions 0 --cleanup-verified
```

Read the current decision report:

```bash
python3 scripts/agent-bridge-benefit-dogfood.py \
  --log "$BENEFIT_DOGFOOD_LEDGER" \
  report | jq
```

## Cross-node content-free aggregate

`export-aggregate` emits no event rows or subject/domain digests. It contains
only the reducer report, a SHA-256 binding to the private local ledger, a
SHA-256 binding to the canonical report, and an operator-supplied salted node
digest:

```bash
python3 scripts/agent-bridge-benefit-dogfood.py \
  --log "$BENEFIT_DOGFOOD_LEDGER" \
  export-aggregate \
  --source-node-sha256 sha256:<private-salted-node-digest> \
  > benefit-aggregate.json
```

This makes an aggregate attributable to one unchanged local ledger without
syncing raw event rows. It does not independently prove operator attestation,
physical pixels, audible sound, or exclusive causation.

An aggregate reports one ledger only. It does not merge samples from multiple
nodes. Raw R4 event rows and ledgers must never be transferred, merged, or
automatically synchronized. Any cross-node source-receipt topology remains a
live-kickoff decision and is not admitted by this source contract.
`source_node_sha256` is an operator-supplied salted label, not independent proof
of node identity.

## Frozen boundaries during the trial

- Qwen remains the default TTS; OmniVoice remains pilot-only.
- Avatar remains foreground and owner-invoked.
- Voice remains default-off and uses fixed lines only.
- No automatic user service, continuous listening, desktop control, new action
  domain, or `embodiment-runtime-p4` authority is admitted.
- No result automatically installs, deploys, merges, pushes, or changes memory
  retrieval/ranking.
