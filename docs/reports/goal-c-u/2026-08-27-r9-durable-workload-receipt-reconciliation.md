# R9 durable workload-receipt reconciliation

Date: 2026-08-27
Status: source-verified candidate; authoritative publication and installed acceptance blocked

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

The implementation commit is `e96f7bd4`, replayed directly onto authoritative
GitLab master `0e6a1a0b`. Source verification passed:

- `cargo test -p ab-agent --lib`: 155 passed;
- `cargo test -p ab-agent workload_cgroup::tests --lib`: 22 passed;
- `cargo test -p ab-store --lib`: 543 passed;
- `cargo test -p ab-store --test workload_receipt_ledger`: 9 passed;
- `cargo test -p ab-bridge workload_receipt_reconciliation::tests --lib`:
  8 passed;
- `cargo test -p ab-bridge body_telemetry::tests --lib`: 23 passed;
- `cargo test -p ab-bridge --lib -- --test-threads=1`: 2087 passed and
  5 pre-existing ignored tests;
- `AGENT_BRIDGE_EMBED_BACKEND=hash cargo test -p ab-bridge --lib`: 2087
  passed and 5 pre-existing ignored tests;
- all-target checks for `ab-agent`, `ab-store`, and `ab-bridge`: passed; and
- `git diff --check`: passed.

The new regression surface exercises pre-START cleanup, root-locked capacity,
active-producer exclusion and lease handoff, interrupted tombstone cleanup,
Store failure before ACK, commit-before-ACK replay, different-projection
Duplicate semantics, mixed-projection/kind and private-field rejection, and
the standalone-only recovery truth boundary. An independent read-only review
found no false-ACK, early-release, or peer-steal blocker. It prompted three
closures before the final gate: the unguarded generic live-commit API was
removed, the deployable manifest was advanced to schema 2 with mandatory
`producer.lock`, and the terminal response cache now releases its operational
lease after its background record attempt.

One default-parallel Bridge run exposed the existing optional-ONNX cold-start
transition in `b3_preflight_excludes_foreign_project_near_duplicates`: the
stored row used the hash fallback while the query switched to ONNX, producing
an empty B3 result. The exact test passed with the deterministic hash backend,
and the complete unpinned single-thread suite passed. No R9 test failed, and
R9 changes do not touch embedding or B3 code.

The remaining source-level liveness limit is explicit: reconciliation runs at
startup, not as a permanent polling service. A peer that crashes after another
Bridge's startup scan waits for the next startup (or another peer startup).
This does not lose or falsely ACK evidence, and adding a background reconciler
would be a separate daemon/authority decision.

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
