# R5 beneficiary-closure dogfood

Status: P1a preregistered on 2026-08-24. Collection starts only after the
P1a profile change is deployed and a fresh host-managed Codex MCP process
lists both `embodiment_record` and `embodiment_snapshot`.

## Decision question

Does the P0 beneficiary-closure surface make real task completion,
verification, rollback readiness, and operator burden less ambiguous at low
ceremony, without inventing owner/harness authority or turning a receipt into
permission to act?

P1a answers only the reachability prerequisite. It adds the existing
record-only receipt writer and reader to the Codex compact tool profile. In
that profile, `embodiment_record` exposes and accepts only
`operation_receipt`; `embodiment_snapshot` exposes only the redacted receipt
ledger and excludes legacy Event Spine facts, body telemetry, and current
write-lease state. `codex-essential`, the inheriting `codex-voice`, and the
composed mobile profile use this restricted shape; non-Codex standard/all
profiles keep their legacy shapes for compatibility. P1a does not change the
envelope, database schema, action path, or authority model.

## Frozen collection window

The decision window starts at the first matching-contract outcome recorded
after all of these are true:

1. the P1a source commit is present in the installed `.real` binary;
2. `doctor --json` has no stale MCP warning for the participating Codex host,
   and every participating daemon/MCP `/proc/<pid>/exe` resolves to and hashes
   as the installed `.real` rather than a deleted or older inode;
3. that host's `codex-essential-mobile-projection` tool list contains
   `session_finalize`, `practical_workflow_scorecard`, `embodiment_record`,
   and `embodiment_snapshot`; and
4. the listed `embodiment_record` schema allows only `operation_receipt`, the
   snapshot declares all three `includes_*` exclusions false, and the
   production receipt ledger is read successfully before the first write.

The window closes at the earlier of 10 matching-contract outcomes or 14
elapsed days.
At least five eligible outcomes across at least two fresh MCP process sessions
are required for a decision. Fewer samples produce `insufficient_evidence`,
not PASS or FAIL. This is a bounded product dogfood sample, not a statistical
performance claim.

Every eligible outcome uses task-outcome input
`contract_id=r5p1a-dogfood-20260824` and `revision=1` (persisted in the ledger
column `contract_revision`). Its `environment_id` is an opaque process token
of the form `mcp_<32 lowercase hex>` generated once per fresh MCP process and
reused only within that process; it contains no hostname, session ID, path, or
user text. Distinct tokens are agent-reported process-boundary evidence, not
authenticated process identity. Other contract IDs, revisions, or missing
process tokens are outside the P1 denominator even when a rolling scorecard
also sees them.

The trial contract is reserved exclusively for eligible natural tasks. Every
persisted row matching its exact ID and revision enters the denominator; rows
may not be cherry-picked by a later natural-task judgment. If a matching row
is later found to be a fixture, quota-filling repetition, dry run, or otherwise
ineligible, the trial fails and that row may not be skipped or replaced.

## Eligible evidence

An eligible outcome belongs to a naturally requested owner task completed in
the ordinary workflow. A test invented to populate the ledger, repeated work
performed only to reach the quota, fixtures, and dry runs are ineligible.
Exactly one immutable outcome ID is assigned to one task attempt. Identical
transport retries may be admitted as duplicates; a conflicting retry is a
gate failure and cannot replace the first row.

An eligible outcome ID has the opaque form
`r5p1a_out_<32 lowercase hex>`. It is a trial selector and correlation handle,
not a task description.

Every public outcome remains `agent_reported`. Public Codex cannot assert
authenticated owner acceptance or harness verification, so acceptance must
remain `unknown`/`unavailable`. User language in chat is not translated into
an authenticated ledger fact.

A body-operation receipt is eligible only when a natural, non-mutating
operation already produced a terminal envelope with fresh, digest-bound
observations and an independent verifier claim. P1 must never perform an
operation merely to create a receipt. If no such operation occurs in the
window, the receipt lane is `insufficient_natural_sample`; it does not block
the outcome-lane decision and does not justify Registry, lease, or executor
work.

At preregistration there is no production `BodyOperationEnvelope` producer.
Making the bounded writer and reader reachable from the compact profile is a
prerequisite for observing a future natural sample, not evidence that such a
sample exists and not a benefit claim.

An eligible receipt uses an opaque operation ID of the form
`r5p1a_<32 lowercase hex>`. This namespace is a trial selector, not a task
description. It is reserved exclusively for naturally produced eligible
receipts. Every persisted row in that namespace enters the receipt-lane
denominator; discovering an ineligible matching row fails the trial rather
than allowing it to be skipped. Receipt rows outside that namespace are
excluded.

Raw prompts, task titles, paths, observation payloads, action arguments,
postcondition text, lease IDs, and memory contents must not enter either
ledger or an aggregate report. IDs are opaque handles and evidence references
are SHA-256 digests.

## Frozen gates

The outcome lane passes only when all of the following hold:

- at least five eligible outcomes span at least two fresh MCP processes;
- at least five eligible outcomes have reported status `achieved`; otherwise
  the verification-quality denominator is insufficient;
- every selected persisted outcome decodes as a valid record, and any
  invalid or conflicting `session_finalize` response observed during capture
  is an immediate gate failure;
- every admitted public record is `agent_reported`, with no public
  owner-attested or harness-verified provenance claim;
- every admitted record explicitly reports all three burden counters, so each
  operator-burden observation count equals the admitted-outcome count;
- at least 80% of the at-least-five reported achieved outcomes are reported
  verified by `tests` or `postcondition` and carry a digest-bound evidence
  reference;
- owner acceptance remains unknown unless a separately authorized,
  authenticated producer is implemented; and
- ordinary capture uses the same single `session_finalize` write call already
  needed for lifecycle closure. A second write call solely to represent the
  task outcome is a ceremony regression.

Manual interventions, owner restatements, and repeated authorization prompts
remain descriptive task-burden facts; this small heterogeneous sample does not
pretend that all three must be zero. The final report must separately call out
any burden caused by the capture schema or retry behavior.

If at least one eligible receipt occurs, the receipt lane passes only when:

- every admitted receipt is terminal, non-mutating, and
  `public_mcp_agent_reported`/`advisory_only`;
- every response reports `executed=false`,
  `authority_authenticated=false`, and
  `projected_to_event_spine=false`;
- any invalid/conflicting receipt response observed during capture is an
  immediate gate failure, while a before/after read confirms that it did not
  write or overwrite a row; and
- the read projection exposes only the bounded redacted facts, with no Event
  Spine projection, body telemetry, or write-lease state.

Any mutation or lease-bearing public receipt being admitted, any automatic
action or receipt generation, any public owner/harness authority claim, or any
raw private payload in durable evidence is an immediate FAIL.

## Readout and decision

The decision denominator comes from a read-only ledger audit, not from the
rolling scorecard. Select outcome rows by the exact contract ID/revision,
order by `(recorded_at, outcome_id)`, set the start to the first selected row,
and retain at most the first 10 rows whose `recorded_at < start + 1_209_600`.
The trial is still open when fewer than 10 rows exist and 14 days have not
elapsed. Select receipt rows by the exact `r5p1a_` operation-ID namespace and
the same half-open time window, ordered by `(recorded_at, operation_id)`.

The final report must publish a content-free canonical manifest containing,
for each selected outcome, only `outcome_id`, `record_sha256`, and
`environment_id`, and for each selected receipt only `operation_id` and
`record_sha256`. Sort as above and publish the SHA-256 of the canonical
manifest so another read-only query can reproduce the denominator and detect
reordering or omission.

The manifest schema is
`agent_bridge.r5p1a_evidence_manifest.v1`, with top-level keys
`schema_version`, `outcomes`, and `receipts`. All values are frozen ASCII
identifiers or SHA-256 strings. Serialize it as UTF-8 JSON with object keys
sorted lexicographically at every level, arrays kept in the ledger order
defined above, and no insignificant whitespace; hash those exact bytes. This
is the only canonical encoding used for the published manifest digest.

Use `practical_workflow_scorecard` as a broader operational sanity read and
the receipt-only `embodiment_snapshot` as the bounded receipt read. Record the
installed version/hash, matching live-process hashes, window bounds, eligible
task count, observed duplicate responses, and any capture-specific ceremony.
The current SQLite ledgers retain admitted first rows, not an attempt journal:
absence of rejected retries cannot be reconstructed from scorecard zeros, and
attempt-level duplicate/invalid/conflict coverage must be labeled
`agent_reported` or `unavailable`. Neither a rolling aggregate nor a process
token authenticates real-task truth; the natural-task label remains an
operating-protocol-constrained agent claim.

PASS means retain the evidence surfaces and consider at most one separately
authorized, read-only P1b improvement grounded in observed friction. FAIL
means revert the P1a profile exposure and keep P0 ledgers intact for audit.
`insufficient_evidence` means keep collection bounded or refreeze R5; it never
authorizes more embodiment machinery.

## Frozen boundaries and rollback

P1 adds no authenticated producer, body/adapter registry, lease TTL or
fencing, durable executor journal, mutation admission, automatic routing,
policy change, or homeostatic action. The existing public mutation/lease
rejection remains mandatory.

The source rollback is removal of `embodiment_record` and
`embodiment_snapshot` from `CODEX_ESSENTIAL_DIRECT_EXTRAS`. Runtime rollback
uses the pre-deployment `.real` backup, restarts the services and every
participating Codex host/MCP child, then verifies matching live executable
hashes and confirms that both tool names disappeared from the compact
`tools/list`. Append-only outcome and receipt rows are audit evidence and are
not deleted by this rollback.

P1 does not backfill, alter, or count toward the R4 owner-local JSONL reducer.
If the same natural task is separately eligible for R4, its R4 event requires
an independent explicit record under the R4 contract.
