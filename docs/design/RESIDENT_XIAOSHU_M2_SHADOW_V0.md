# Resident Xiao Shu M2 shadow v0

Date: 2026-08-25 (America/Los_Angeles)

Status: approved bounded implementation and read-only review gate, deployed
2026-08-25. This is a default-off policy evaluator, optional private report
ledger, and evidence aggregator. It is not M2 runtime admission.

## Decision and purpose

The R7-E1 owner label `useful` supplied the positive M1 value signal required
to review one separate M2 shadow slice. The smallest useful next increment is
to answer one question without creating a new runtime:

> Given an explicitly supplied, typed candidate, would a sparse wake have
> passed a frozen attention and cost policy?

Agent-Bridge owns this deterministic decision and its content-free receipt.
It does not own candidate discovery in this slice. A caller must explicitly
provide the trigger type, timestamps, evidence status, foreground state, and
content hashes. In particular, AB does not infer commitments or due dates from
free text, model output, memory, or project state.

The command is:

```text
agent-bridge resident shadow \
  --basis-wake-id <useful-evaluated-wake> \
  --trigger-kind <commitment-due|recovery|failure> \
  --signal-sha256 <sha256> \
  --evidence-sha256 <sha256> \
  --evidence-status <verified|not-verified|unknown> \
  --observed-at-unix-ms <timestamp> \
  --foreground-state <active|inactive|unknown> \
  --utc-offset-minutes <offset>
```

`commitment-due` additionally requires `--due-at-unix-ms`. Failure candidates
may set `--severity`; only warning or critical failures can be hypothetically
eligible. Preview is the default. `--record` is a separate explicit choice.

## Frozen policy revision 1

| Control | Value | Fail-closed behavior |
|---|---:|---|
| Quiet hours | 22:00-08:00 candidate-local | suppress |
| Foreground session | only explicit `inactive` is eligible | active or unknown suppresses |
| Evidence | only explicit `verified` is eligible | not-verified or unknown suppresses |
| Duplicate signal horizon | 24 hours | same trigger kind and signal hash suppresses |
| Minimum projected-wake interval | 6 hours | suppress |
| Daily budget | 2 projected wakes per candidate-local day | suppress |
| Recovery freshness | 6 hours | stale recovery suppresses |
| Failure freshness | 1 hour | stale failure suppresses |
| Failure severity | warning or critical | info suppresses |
| Hypothetical provider deadline | 120 seconds | reported only when `would_wake=true` |

An eligible decision reports one *projected* provider call. Every report,
including an eligible one, records `actual_provider_calls=0` and
`actual_wakes_created=0`. The implementation has no provider or wake-creation
call site.

## Admission and stop binding

Every evaluation must bind to an existing R7-E1 receipt whose completed wake,
subject, final-output hash, and execution-receipt hash still validate and whose
fixed owner label is `useful`. The candidate evaluation timestamp may not
predate that receipt.

Before evaluating, AB scans the private owner-evaluation ledger. A
`distracting` or `harmful` label recorded at or after the useful basis stops the
entire shadow lane. It returns an error rather than a hypothetical decision.
`neutral` creates no new admission. Labels remain explicit local CLI
assertions, not cryptographic owner authentication, and no recommendation
executes automatically.

## Receipt and privacy boundary

The report schema is `agent_bridge.resident_m2_shadow.v0`. A report contains:

- subject, basis wake, basis evaluation, and the SHA-256 of the bound
  evaluation receipt;
- typed trigger, timestamps, UTC offset, severity, foreground state, evidence
  status, signal hash, and evidence hash;
- the complete frozen policy revision, decision, suppression reasons, and
  explicit non-authority boundary.

It contains no raw signal, raw evidence, prompt, provider response, arbitrary
note, owner identity, or action payload. The command neither reads nor accepts
raw signal/evidence content. Caller assertions are intentionally recorded as
not cryptographically authenticated.

Recorded reports live below the shared private resident root in a 0700
`m2-shadow-reports` directory. Each final JSON file is mode 0600 with one link.
Complete bytes are synced under a private temporary name, then published by an
atomic no-overwrite link. Repeating the exact candidate is idempotent; a
different report at the same deterministic ID fails closed. Preview creates
neither the directory nor a receipt.

Continuity hardening adds a separate 0700 `m2-shadow-report-anchors`
directory. Every newly recorded report receives one 0600 no-replace anchor
binding its report ID and stable state-root-local `ledger_id` to the SHA-256 of
the exact report bytes. The ledger identity itself is a 0600 atomic no-replace
receipt, and read-only review exposes it. History and review require a
one-to-one report/anchor set and fail closed when either side is missing, an
extra anchor exists, the ledger identity differs, or the digest differs. An exact idempotent
`--record` replay may backfill the anchor for a pre-anchor report after
revalidating its schema, deterministic ID, owner basis, and exact bytes; it
does not rewrite the report. This detects local ledger discontinuity but does
not merge state roots or claim cross-node continuity.

## Explicit non-capabilities

This slice has no daemon, scheduler, timer, service, hook, autostart, event
watcher, provider invocation, cognitive wake, tool/action execution, Avatar or
voice projection, external message, runtime configuration change, automatic
memory promotion, or candidate discovery. It grants no OS, network, account,
credential, or device authority. It does not admit M2.

`would_wake=true` is a counterfactual policy result, not permission to wake.
The terms `projected_provider_calls` and `projected_provider_timeout_secs` are
estimates under this frozen shadow policy, not observed execution.

## Measurement and next gate

Collection is not passive: without explicit submission no reports accrue.
The working agent, rather than the owner, handles candidate identification
and submission during ordinary foreground work using
`../operations/R7_ASSISTED_SHADOW_COLLECTION.md`. This operating procedure
does not add automatic candidate discovery or change the frozen policy.

Retain only privacy-minimal reports for real, manually identified candidates.
Classify every retained report explicitly at review time, then review:

- eligible versus suppressed counts by typed trigger;
- suppression reasons, especially foreground collision and quiet hours;
- duplicate, interval, and daily-budget pressure;
- candidate age and evidence-verification failures;
- owner labels on any later explicit M1 wakes; and
- false-positive, stale, distracting, or harmful candidate reports.

The read-only review command is:

```text
agent-bridge resident shadow-review \
  --natural-report-id <real-task-report> \
  --mechanics-report-id <technical-acceptance-report>
```

Both options are repeatable. The natural/mechanics classification is an
explicit invocation-local operating assertion: it is neither persisted nor
cryptographically authenticated. Every report currently in the private
ledger must be classified for the packet to become ready; leaving reports
unclassified cannot produce a partial or cherry-picked ready result. Unknown,
duplicate, or overlapping report IDs fail closed.

The review packet remains `collecting` until all of the following are true:

- at least three natural real-task reports exist;
- those reports cover at least two distinct typed trigger kinds;
- at least one natural report says `would_wake=true`;
- at least one natural report was suppressed;
- every report retains a valid useful-owner basis and the exact safe boundary;
- aggregate actual provider calls and wakes remain zero; and
- no later `distracting` or `harmful` owner label is active.

A passing packet says only
`owner_review_of_candidate_source_design_only`. It hard-codes
`m2_admitted=false` and grants no source, schedule, provider, wake, tool,
action, runtime, or memory authority. The command acquires no writer lease and
does not create, rewrite, relabel, or touch report files.

Source tests and mechanics reports prove mechanics, not unattended-wake value.
The 2026-08-25 worktree-continuity recovery remains a documented natural
observation. The 2026-09-08 audit recovered matching original bytes in the
legacy Linux root, but that root has no ledger identity or anchors. It still
does not count toward the current Mac durable threshold and must not be
silently merged into that ledger. The current macOS ledger is anchored under a stable
`ledger_id`. It contains one legacy mechanics report and one durable natural
failure report produced by an unplanned wrapper-bypass configuration failure
in the real replay workflow. That natural report was suppressed because the
owner session was active, so the natural-suppression criterion is satisfied.
The evidence gate still lacks two more genuine natural reports, a second natural
trigger kind, and one natural `would_wake=true` decision. These are threshold
gaps, not an obligation to keep an active sample-collection goal. Until the frozen
threshold is met, adding discovery, a timer, a scheduler, or any real provider
invocation is prohibited.

On 2026-09-08, active M2 sample pursuit was placed on HOLD after the
owner-authorized stagnation review. An active owner foreground session always
adds a suppression reason, so the foreground-active path cannot
close the natural-true criterion. Truthful inactive inputs remain possible in
the code; global unreachability is not claimed. Existing M0/M1 use and natural
foreground diagnostics remain available. The reopening condition is an
independently occurring, costly, eligible inactive event through an existing
admitted entry, with all original constraints intact. See
[`2026-09-08-validation-collection-closeout.md`](../reports/goal-c-u/2026-09-08-validation-collection-closeout.md).

Two increments without observed use-value refreeze the lane. Any stop label,
raw-content persistence, unexpected provider/tool event, wake creation,
permission weakening, or report corruption stops collection immediately and
preserves evidence for disable or rollback review.
