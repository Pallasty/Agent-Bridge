# Agent-Bridge benefit dogfood V1

Status: source-only implementation; no daemon integration, scheduler, service,
Avatar launch, voice enablement, action authority, deployment, or runtime
influence.

## Decision

The next Agent-Bridge stage is a two-week real-workflow value trial. It asks
whether the already shipped continuity and embodiment surfaces reduce owner
coordination cost without adding distraction, duplicated external actions, or
new authority. It does not ask whether another model, renderer, protocol, or
memory ranker can be built.

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

The reducer returns:

- `COLLECTING_TWO_WEEK_DOGFOOD` while any evidence minimum is unmet;
- `STOP_AND_REVIEW` immediately for harmful recall, duplicated external action,
  or an embodied safety failure;
- `READY_FOR_OWNER_ADOPTION_REVIEW` only when all four gates pass;
- `RETAIN_ON_DEMAND` when the sample is complete but one or more value gates
  fail.

No verdict changes runtime behavior. Even a fully passing report requires a
separate owner adoption decision.

## Local ledger

The default ledger is:

```text
~/.local/state/agent-bridge/dogfood/benefit-v1.jsonl
```

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
python3 scripts/agent-bridge-benefit-dogfood.py record-continuity \
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
python3 scripts/agent-bridge-benefit-dogfood.py record-avatar \
  --attest-real-task \
  --receipt /private/path/linux-live-receipt.json \
  --owner-rating helpful \
  --physical-display-confirmed
```

Record the voice portion of a receipt separately so the same underlying receipt
can contribute to both Avatar and voice gates without duplicating either event
type:

```bash
python3 scripts/agent-bridge-benefit-dogfood.py record-voice \
  --attest-real-task \
  --receipt /private/path/linux-live-voice-receipt.json \
  --worker-state warm \
  --audible-confirmed
```

Record one paired embodied task:

```bash
python3 scripts/agent-bridge-benefit-dogfood.py record-embodied \
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
python3 scripts/agent-bridge-benefit-dogfood.py report | jq
```

## Cross-node content-free aggregate

`export-aggregate` emits no event rows or subject/domain digests. It contains
only the reducer report, a SHA-256 binding to the private local ledger, a
SHA-256 binding to the canonical report, and an operator-supplied salted node
digest:

```bash
python3 scripts/agent-bridge-benefit-dogfood.py export-aggregate \
  --source-node-sha256 sha256:<private-salted-node-digest> \
  > benefit-aggregate.json
```

This makes an aggregate attributable to one unchanged local ledger without
syncing raw event rows. It does not independently prove operator attestation,
physical pixels, audible sound, or exclusive causation.

## Frozen boundaries during the trial

- Qwen remains the default TTS; OmniVoice remains pilot-only.
- Avatar remains foreground and owner-invoked.
- Voice remains default-off and uses fixed lines only.
- No automatic user service, continuous listening, desktop control, new action
  domain, or `embodiment-runtime-p4` authority is admitted.
- No result automatically installs, deploys, merges, pushes, or changes memory
  retrieval/ranking.
