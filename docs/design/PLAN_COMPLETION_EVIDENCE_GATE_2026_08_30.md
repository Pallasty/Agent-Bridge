# Plan Completion Evidence Gate

Status: strict producer integration HOLD; ordinary-plan compatibility authorized
2026-09-09.

## Ordinary maintenance compatibility (2026-09-09)

Plans persist a `completion_mode`: `agent_reported` or `evidence_gated`.
New plans default to `agent_reported`; omitted mode on an existing plan preserves
its mode. An explicit conflicting mode change is rejected. Ordinary completion
retains the existing nonempty status-label workflow and needs no outcome record.
It is reported completion, never independent verification.

For pre-mode rows, inference uses raw persisted anchors/evidence, not hydrated
contracts. Any persistent strict binding forces `evidence_gated`, even if the
mode field says otherwise; malformed strict evidence cannot fall back to reported
completion. Both write paths, load projections, progress, and next-step selection
use the effective mode. Ordinary `done` contributes to reported progress but
not `verified_done_count`.

The owner authorized this compatibility repair so ordinary maintenance releases
can proceed without a trusted completion producer. The strict rules below remain
unchanged for `evidence_gated` plans. The producer NO-GO and natural-task reopen
gate remain in force.

## Decision

In an `evidence_gated` plan, `PlanStep.status = "done"` is a verified state transition, not an agent-authored
label. Both plan write paths (`plan_save` and `plan_update`) use the same
fail-closed Store gate. A transition is admitted only when:

1. every declared dependency is already evidence-gated `done`;
2. the caller names an immutable `AgentTaskOutcomeRecord` by ID (a
   round-tripped record digest is checked but conveys no authority);
3. the outcome is structurally and digest valid;
4. its contract is bound to the current plan ID, step ID, description, and
   sorted dependency set;
5. it reports `achieved` + `verified`, has a concrete verification method and
   evidence digest, and carries `harness_verified` provenance.

The dependency check, outcome lookup, and plan write occur in one SQLite
`IMMEDIATE` transaction. In v1, an evidence-gated `done` is terminal: it cannot
be reopened, removed from the same plan, or rebound to a different outcome.
This prevents an old outcome from being replayed after purported rework. A new
attempt must be represented by a new step/contract until a durable generation
scheme exists. Legacy evidence-free `done` rows remain repairable.

On admission, the Store also persists `completion_anchor = true` beside the
evidence reference. This is a Store-owned, irreversible marker: callers may
round-trip it, but a submitted value is cleared and recomputed, so it cannot
mint completion authority. The independent marker keeps the terminal rule in
force even if the step status or evidence reference is later malformed. For
backward compatibility, a valid pre-marker evidence reference is itself an
anchor and is projected with the marker set.

## Contract identity

Each step receives a revision-1 content-derived contract:

```text
plan-step:<sha256(length-frame(
  domain_tag,
  revision,
  plan_id,
  step_id,
  desc,
  dependency_count,
  sorted_dependencies...
))>
```

Every value is length-prefixed before hashing, so field boundaries are
unambiguous; dependency order in caller JSON is intentionally not semantic.

Changing the step's meaning or dependency set therefore invalidates an older
outcome instead of allowing it to be replayed against a replacement step.

## Truth boundary

The v1 gate deliberately rejects:

- public `session_finalize` outcomes, whose provenance is `agent_reported`;
- `owner_attested` outcomes, until an authenticated owner-producer policy is
  defined separately;
- `BodyOperationReceiptRecord`, which is explicitly advisory-only;
- workload custody receipts, which prove workload lifecycle rather than the
  semantic task postcondition;
- caller-supplied verification/provenance JSON.

The public MCP route therefore cannot manufacture its own green result. It can
only request a transition using an outcome already admitted by a trusted
harness producer. The absence of such a producer fails closed; adding an
authenticated producer is a separate organ and authority decision.

## Producer admission review

A read-only review on 2026-08-30 found real use of the plan consumer but no
production source of trusted completion. The live node contained 48 plans and
202 `plan_save`/`plan_load`/`plan_update` calls in the preceding 30 days. Its
outcome ledger contained 31 rows, all `agent_reported`; it contained zero
`harness_verified` rows. This establishes that persistent planning is a real
workflow, but it does not establish demand for an automatic trusted producer.

The production writer inventory is closed:

| Candidate path | What it proves | Why it cannot close a plan step |
|---|---|---|
| public `session_finalize` | an agent-reported task claim | admission forces `agent_reported` and rejects harness/owner provenance |
| body-operation receipt | a structurally valid advisory receipt | verifier identity and truth are still caller claims |
| workload receipt/reconciliation | process-tree custody and resource accounting | no semantic task postcondition |
| session/process wait | terminal lifecycle and exit status | exit is not task success |
| desktop/audio/Focus-follow observers | a bounded observed postcondition in their own domain | no exact plan-contract binding or trusted outcome writer |
| durable `app_control(action="next")` | allowlisted dispatch plus a stable changed track ID | closest candidate, but not contract-bound and not backed by a natural plan-completion need |
| test fixtures/direct Store calls | gate mechanics | synthetic and unauthenticated outside the test process |

The 2026-08-30 decision was **NO-GO for a producer and HOLD for runtime rollout**.
The source contract and regression tests remain useful as a fail-closed
boundary, but that unconditional-gate build must not replace the ordinary deployed plan workflow:
without a producer, every new `done` transition is intentionally unavailable.
No service, scheduler, verifier command runner, second ledger, public
provenance field, or generic Recuris runtime is admitted by this result.

### Reopen gate

Producer work may be reconsidered only when one naturally occurring plan task
simultaneously supplies all of the missing evidence: a concrete owner/workflow
cost from ambiguous completion, a closed machine-verifiable postcondition, an
already useful observer independent of the agent's claim, and a Bridge-owned
write seam that can be narrowed to that observer. Fixtures, dry runs, tasks
invented to populate the ledger, and generic natural-language plan
descriptions do not count. Existing workflow telemetry or an explicit owner
report may corroborate the need; no new collector or synthetic dogfood window
is required to manufacture it.

The first admitted producer must then be one default-off allowlisted adapter
for that task family. It must bind the exact Store-derived plan contract before
execution, accept only an installed and integrity-checked observer, persist
only canonical evidence digests, and complete at least one eligible shadow
comparison for the reopening natural task with zero false-green results. One
false green, a need for caller-supplied verifier commands, or an authority
requirement broader than the single observer refreezes the lane.

The retained implementation candidate is the existing durable MPRIS `next`
transaction: "advance one specified player exactly once and observe a stable,
different track ID." It is a design seam, not an active goal. It may be wired
only if that exact task occurs naturally and satisfies the reopen gate.

## Compatibility and legacy rows

The contract and completion fields are additive `serde(default)` fields inside
the existing `steps_json`; no SQLite migration or second ledger is introduced.
Legacy plans remain readable. A legacy step whose literal status is `done` but
which has no accepted completion reference is reported as
`legacy_unverified`, does not count in verified progress, and cannot satisfy a
dependency. Re-saving a plan cannot use such a row to bypass the gate. If a
persisted completion anchor exists but its exact outcome, contract, or digest
later fails validation, reads clear it only in the fail-closed projection and
return a structured `completion_diagnostics` entry; this is reported as an
`integrity_failure`, not mislabeled as legacy data.

The detectable integrity boundary is explicit. A persisted marker without a
valid `done` state and exact evidence reference is an integrity failure and
still cannot be reopened, deleted, or rebound. If an external actor can rewrite
`steps_json` and erase both the marker and the evidence reference together,
however, that row is indistinguishable from a genuine legacy row. Detecting
that class of wholesale row rewrite (or a database rollback) requires a future
authenticated plan-row digest or a separately protected immutable anchor
mapping. The same limitation applies if an external actor coherently replaces
both `outcome_id` and `record_sha256` with another valid outcome for the same
contract: the colocated boolean marker does not retain the former outcome
identity. V1 does not pretend the colocated JSON fields are protection against
an actor who can coherently rewrite the database itself. By contrast, a partial
reference rewrite (ID or digest alone) is detectable and cannot be "repaired"
through either plan mutation API.

New writes normalize the accepted state vocabulary:

| Input | Stored state |
|---|---|
| `NOT_YET`, `pending` | `pending` |
| `IN_PROGRESS`, `in_progress` | `in_progress` |
| `DONE`, `done` | `done` (evidence required; terminal in v1) |
| `BLOCKED`, `blocked` | `blocked` |
| `OBSOLETE`, `obsolete`, legacy `cancelled` | `obsolete` |

## Deliberate non-goals

- no Recuris runtime or parallel task ledger;
- no execution of verifier commands from plan data;
- no trust in MCP session hints as actor authority;
- no inference that process exit, tool success, or receipt existence proves the
  step's postcondition;
- no silent upgrade of historical `done` rows;
- no reopen generation/nonce ledger in v1; terminal completion is the replay-safe
  boundary until that authority model is designed;
- no authenticated plan-row integrity envelope; simultaneous external removal
  of both the completion marker and evidence reference, or coherent replacement
  of both evidence identity and digest, is outside the v1 detectable boundary.
