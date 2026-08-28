# R9 durable workload-receipt reconciliation

Date: 2026-08-27
Status: source candidate under verification; authoritative publication and installed acceptance blocked

## Outcome

The R9 candidate implements the bounded process-restart closure between Linux
delegated-cgroup terminal accounting and AB's durable semantic memory. A
body-bound local workload now
has a manifest-bound private outbox entry before START, a terminal receipt only
after recursive `populated=0` and counter capture, one atomic SQLite
ledger/event commit, and an idempotent filesystem acknowledgement afterwards.

This is an exactly-once durable commit claim with a replay-safe ACK effect. It
is not an exactly-once filesystem-delivery claim, hostile same-UID containment,
or reconstruction of process-local body observations.

## Product problem and measure

The concrete code-level failure mode was a Bridge stop after the supervisor had
obtained the best available whole-workload evidence but before the owning
process had recorded its body-span event. Losing that evidence either made the
result permanently Unknown or required repeating useful work solely to recover
telemetry.

The acceptance measure is:

- a restart at the commit/ACK boundary requires zero workload reruns;
- exact replay changes receipt-ledger and semantic-event row counts by zero;
- an ownerless manifest without a valid terminal receipt never becomes
  Complete; and
- restart projection remains standalone workload accounting and never claims
  recovered body before/after observations or a reconstructed
  `task_span_closed` event.

## Implemented source boundary

- Bridge creates the opaque body span before launch and passes it in a reserved
  launch-control field that the Agent consumes and removes from both explicit
  and ambient payload environments.
- Agent durably allocates a bounded private manifest entry before START and
  holds a close-on-exec exclusive producer lease through live commit/ACK.
- A prepared launch dropped before START removes only its known files and empty
  entry; after START, absence or age never authorizes cleanup or completion.
- The supervisor seals PID-free cgroup aggregates only after terminal
  emptiness, then atomically publishes and syncs the receipt before exiting.
- Store uses an immediate transaction for immutable receipt rows, one bound
  semantic event, and ring pruning. Conflict writes nothing; exact duplicate
  replay writes no second event.
- When a batch adds any row, Store validates its single span and canonical
  public projection, the event target/facts binding, and privacy constraints
  before authorizing ACK. An all-duplicate replay is authorized by its existing
  immutable row/event and does not validate, insert, or claim the later
  requested projection.
- Startup reconciliation skips actively leased entries without delaying a new
  Bridge. Released but unsealed entries receive a bounded sealing grace and
  remain `receipt_commit_unknown` if no valid receipt arrives.

## Truth and privacy limits

The restart event is `workload_receipt_reconciled`, with recovery scope
`standalone_workload_accounting`. It stores no nonce, unit, PID, pidfd, cgroup
path, socket or spool path, command, environment, prompt, or transcript. The
same-UID cooperative custody boundary from the delegated-cgroup design is
unchanged.

Session IDs and the complete active body span are not durably reconstructed in
this increment. Persisting those would be a separate organ with a separate
value and privacy review.

## Verification ledger

The final source gate must include Agent durable-spool and full library tests,
Store ledger and full library tests, Bridge reconciliation/reserved-binding/
cgroup-body tests, and all-target compile checks. It must exercise pre-START
cleanup, capacity admission, producer ownership handoff, Store failure,
commit-before-ACK replay, projection mismatch rejection, and privacy checks.

Source verification does not satisfy the installed gate. Required live
acceptance is one authoritative build, explicit restart of daemon,
daemon-http, and Palace, executable-hash alignment, both health endpoints,
Doctor, fresh-MCP admission, a commit-before-ACK restart/replay exercise, and
absence of residual spool entries or transient scopes.

## Current blocker

The candidate worktree is based on the readable GitLab authoritative master,
but this node currently has no authenticated push path to an authoritative
remote. The installed services therefore remain outside this candidate, and
R9 is not deployed or live-admitted. A local file remote or an unproven binary
override is not an equivalent publication authority.
