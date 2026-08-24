# Agent Beneficiary Closure V1

Status: P0 source merged and deployed on 2026-08-24 as an evidence-only
runtime slice. P1a is limited to making the already implemented record-only
receipt write/read surfaces reachable from the deployed Codex compact profile.
Neither status authorizes executor enablement, service-side action, or
production embodiment admission. Runtime truth requires the installed
binary's version/hash, `doctor`, and matching live-process executable identity
and hashes; this source document alone is not runtime evidence.

## Product position

Agent-Bridge has two compatible product descriptions:

1. **Agent Continuity & State Plane**: durable, privacy-minimal state that lets
   an agent resume work, preserve decisions, report outcomes, and distinguish
   evidence from lifecycle proxies.
2. **Digital-embodiment continuity core for agents**: a common contract for
   binding an agent, body adapter, observation, authority lease, operation,
   verification, recovery decision, and memory evidence across one bounded
   action.

The second description extends the first; it does not replace it. A body is an
addressable capability boundary with observation and actuation adapters, not a
claim that Agent-Bridge is conscious or that it is an operating-system
scheduler.

V1 closes two evidence gaps without adding a new MCP tool: an explicit task
outcome can accompany `session_finalize`, and a terminal body-operation
receipt can accompany `embodiment_record`.

## Implemented source contracts

### Explicit task outcome closure

`session_finalize` accepts an optional
`agent_bridge.agent_task_outcome.v1` object. Omitting it preserves the existing
lifecycle-finalization behavior. Supplying it adds a bounded outcome claim
with:

- an opaque outcome ID and task-contract ID/revision;
- a closed result and verification status;
- an explicit verification method, evidence digests, and claim provenance;
- a closed rollback disposition; and
- independently optional counts for manual interventions, owner restatements,
  and repeated authorization prompts.

The public `session_finalize` producer is deliberately untrusted for owner and
harness identity. It accepts only `provenance=agent_reported`, fixes user
acceptance to `unknown`/`unavailable`, and limits verification methods to
`tests`, `postcondition`, or `none`. Broader owner/harness enum values are
reserved for a future authenticated producer; no current public MCP call can
write them.

Accepted records enter the dedicated `agent_task_outcomes` SQLite ledger. The
ledger carries an explicit row schema version and is append-only at the
outcome-ID boundary. The SQLite transaction compares immutable semantic fields
as well as the canonical digest: an identical retry is a duplicate, while the
same outcome ID with different content is a conflict and cannot overwrite the
first record. Caller-provided MCP session hints are not stored. A finalization
call is not itself evidence that a task succeeded.

The store boundary revalidates closed sets, identifier/digest bounds,
cross-field rules, and the canonical record digest; opening the store also
verifies the dedicated table shapes. A malformed persisted evidence cell is
isolated as one invalid row instead of aborting the whole scorecard read.

Ledger admission is an independent durable transaction before maintenance.
`dry_run` performs a read-only duplicate/conflict check. If later memory
maintenance or export fails after a real admission, the response is an
explicit `partial_failure` containing the outcome write status; retrying the
same immutable claim returns `duplicate` rather than hiding the earlier
commit. Runtime validation bounds the compaction horizon and safely converts
it to seconds before outcome admission, so malformed maintenance arguments
cannot create an unreported partial commit.

`practical_workflow_scorecard` reads this ledger and labels every resulting
dimension `reported_*`: these are claims with visible provenance, not
authenticated goal-result, verification, or acceptance truth. Existing
bootstrap-follow-up, finalize, plan-update, and recovery signals remain
labeled as proxies. Operator-count totals appear only for fields actually
reported, with per-field observation coverage; missing data is never converted
to zero. The public producer therefore reports acceptance as unknown until a
future authenticated owner channel exists.

The table is an admitted-record ledger, not an attempt journal. Rejected
invalid or conflicting calls are not durably enumerated, so a scorecard zero
cannot prove that no rejected retry occurred. Attempt-level coverage remains
agent-reported or unavailable until a separately designed, privacy-bounded
attempt audit exists.

### Body-operation evidence envelope

`agent_bridge.body_operation_envelope.v1` defines a portable
`BodyOperationEnvelope`. Its validator makes five embodied-operation
invariants concrete:

| Invariant | V1 evidence rule |
|---|---|
| No fresh observation, no action | The pre-observation is body/source-bound, canonically content-digested, and fresh at the declared action-start time under a server cap of 60 seconds. Action start/completion and post-observation ordering are explicit, so a delayed receipt retry does not redefine freshness. |
| No authority/lease, no mutation | The portable contract requires a lease for mutation. The public MCP record route has no authenticated principal or fenced lease, so it rejects every mutation receipt instead of treating caller-supplied session/lease strings as authority. |
| No operation ID, no retryable side effect | Every envelope has a stable opaque operation ID. A dedicated SQLite table uses it as a primary key and atomically classifies identical content as duplicate or different content as conflict, including concurrent and old retries. This protects receipt admission, not actuator execution. |
| No independent postcondition verification, no success | Structurally, `succeeded` requires a later, canonically content-digested observation attributed to a verifier identifier/build distinct from the action adapter; `verified` cannot accompany failed/abandoned status. These adapter identities remain caller claims until a trusted registry attests them. |
| No provenance/freshness, advisory only | Missing or mismatched structural provenance/freshness fails validation. Every receipt accepted from public MCP is nevertheless stored as `public_mcp_agent_reported`/`advisory_only`, never as an authenticated green Event Spine verdict. |

In V1 these are a portable structural contract and receipt-admission
conditions, not an actuator interlock. Canonical hashes detect content changes
inside the submitted envelope but do not authenticate who produced it. An
adapter migration, server-side principal, signed or registered adapter
attestation, and separate runtime authorization are required before these
rules can prevent an attempted action rather than reject or label evidence
afterward.

`embodiment_record(kind="operation_receipt")` validates a terminal envelope
and writes only a redacted projection to the dedicated
`body_operation_receipts` ledger. It deliberately does not project the public
claim into Event Spine, because a caller-declared verifier must not become a
`Verified` verdict. Raw observation payloads, action arguments, postcondition
text, memory contents, MCP session hints, and raw lease IDs are not persisted.
The tool records facts only: it never executes, resumes, retries, rolls back,
or authorizes an action.

P1a exposes `embodiment_record` and `embodiment_snapshot` in
`codex-essential` (and therefore the composed
`codex-essential-mobile-projection` profile) so Codex can actually dogfood
this P0 evidence path. Both names are profile-scoped there: the record schema
and handler accept only `operation_receipt`, while the snapshot returns only
the redacted receipt ledger and explicitly excludes legacy Event Spine facts,
body telemetry, and write-lease state. Broader profiles retain their legacy
surface for compatibility. This is new reachability to an existing evidence
capability, not new execution or authorization authority: the same public
handler continues to reject mutation or lease-bearing receipts, and no
automatic producer or lifecycle hook is added.

No production `BodyOperationEnvelope` producer exists at P1a
preregistration. Profile reachability cannot itself create a natural receipt
sample or establish user benefit.

The store boundary admits only the fixed canonical redacted-facts shape and
recomputes its digest, so a direct store caller cannot add arbitrary fields or
reuse a forged digest to bypass conflict detection. Store open also verifies
declared column types, nullability, primary-key positions, and the owner/column
layout of the dedicated indexes, failing closed on a colliding table shape.

The ledger makes receipt recording atomic and retry-safe across the node-local
database. It is not executor-level idempotency and does not replace a durable
action journal. A future trusted mutation producer must couple fenced
authorization, execution, and receipt/journal state with its own recovery
contract before runtime admission.

## Evidence ownership and non-duplication

Each existing evidence surface keeps one narrow job:

- `agent_task_outcomes` is the general operational ledger for explicit task
  result claims consumed by `practical_workflow_scorecard`.
- `scripts/agent-bridge-benefit-dogfood.py` and its owner-local JSONL ledger
  remain the locked V1 adoption experiment for continuity, Avatar, paired
  embodied, and Qwen voice samples. The SQLite outcome ledger neither
  backfills nor changes those gates.
- `tool_atlas_snapshot` and `mcp_dispatch_audit` remain authoritative for tool
  surface, usage, failures, latency, and payload pressure.
- `body_operation_receipts` is the atomic, advisory public receipt ledger;
  legacy embodiment kinds continue to use Event Spine, which is neither an
  action journal nor trusted operation-verification authority.

V1 therefore adds no automatic tool router and no duplicate tool-health
scoring system. A later recommender may consume Tool Atlas facts, but it must
remain read-only until a separate measured adoption decision authorizes more.

## Privacy and authority boundaries

IDs in both contracts are opaque correlation handles, not places for task
titles, prompts, project names, host names, paths, or personal text. Evidence,
request, postcondition, rollback, adapter-build, and memory references are
content digests. Aggregates should expose counts and closed states rather than
raw digests unless a bounded audit explicitly needs them.

These source contracts do not provide:

- consciousness, subjective experience, or a standard claim of human-like
  embodiment;
- operating-system resource scheduling or process supervision;
- permission to mutate a desktop, application, device, network, or external
  API;
- a production `BodyRegistry`, production actuator-adapter registry, or
  cross-process lease service;
- lease TTL, renewal, fencing tokens, or durable action-journal recovery; or
- evidence that this branch is built, installed, enabled, deployed, or active
  in any particular live Agent-Bridge process without a matching installed
  version/hash, `doctor` observation, and live executable identity/hash.

An envelope proves only that its submitted fields satisfy the V1 structural
contract and canonical content bindings. It does not prove adapter identity,
owner identity, independent execution, or authority. Authority still comes
from an authenticated owning harness and runtime policy; a record never
manufactures it.

## Source anchors

- `crates/bridge/src/agent_task_outcome.rs` owns the closed task-outcome schema,
  validation, canonical digest, and digest-free aggregation.
- `crates/store/src/lib.rs` and `crates/store/src/sqlite.rs` own the immutable
  outcome and operation-receipt rows, atomic duplicate/conflict admission,
  explicit row schemas, and dedicated SQLite persistence contracts.
- `crates/world-core/src/body_operation.rs` owns the portable body-operation
  envelope and invariant validator.
- `crates/bridge/src/mcp_tools.rs` integrates the contracts into the existing
  `session_finalize`, `practical_workflow_scorecard`, and
  `embodiment_record` surfaces.

## Phased extension path

Further work remains gated by real use and separate runtime authorization:

1. **Registry and leases**: add a production `BodyRegistry` and typed adapter
   registry, then replace process-local lease assumptions with TTL, renewal,
   fencing tokens, holder identity, and durable expiry evidence.
2. **Migrate the strongest existing loop first**: adapt
   `desktop_semantic_task` to the envelope because it already approximates
   observe-act-verify. Migrate `app_control` second, preserving its durable
   operation journal and idempotent recovery semantics.
3. **Hold broader control**: do not migrate `system_control` mutations until
   each admitted action has a specific postcondition and an independent
   observer capable of verifying it.
4. **Harness receipts and approvals**: bind approvals, denials, retries, and
   terminal harness receipts to operation and outcome IDs. Owner acceptance
   must remain explicit rather than agent-inferred.
5. **Read-only homeostasis**: combine explicit outcomes, Tool Atlas pressure,
   retry loops, lease health, and verification coverage into advisory
   recommendations. It may propose re-observation, surface contraction, or
   escalation, but may not route tools, mutate policy, or trigger action.

Every phase must keep the ordering `observe -> authorize -> identify -> act ->
independently verify -> record/recover`, preserve content-minimal evidence, and
stop before runtime enablement unless the owner separately authorizes it.
