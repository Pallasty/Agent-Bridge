# Engram G1.4 Public-Synthetic Protocol Harness

Date: 2026-07-18

Status: **IMPLEMENTED IN PUBLIC SYNTHETIC LAB / DEFAULT OFF / NO NATIVE SANDBOX OR EXPERIMENT AUTHORITY**

## Decision

This gate implements the closed G1.4 protocol as an in-memory, public-synthetic
state machine. It proves that candidate locks, bounded feedback, arm blinding,
sandbox-attestation shape, deterministic qualification, one-shot execution,
fixed decision guards, append-only receipts, and rollback-lesson requirements
can be exercised together without opening a real experiment.

It does not implement the candidate, launch a process, call `nono`, install
Landlock or Seatbelt policy, inspect kernel enforcement, accept a real freeze
capability, read FIT/development/sealed data, unblind a result, mutate
retrieval, write the live store, register an MCP/runtime surface, deploy code,
or promote behavior.

The gate is disabled unless `exercise --enable-public-synthetic` is supplied.
Its registered fixture is immutable public JSON and is not production
admissible. The one positive boundary fact is
`public_synthetic_protocol_harness_implemented=true`; every real access,
execution, native-enforcement, release, mutation, write, and promotion bit is
false.

## Registered artifacts

- contract:
  `scripts/eval/fixtures/engram_g14_public_synthetic_protocol_harness_contract_v0.json`;
- fixture:
  `scripts/eval/fixtures/engram_g14_public_synthetic_protocol_harness_fixture_v0.json`;
- implementation:
  `scripts/eval/engram_g14_public_synthetic_protocol_harness.py`;
- adversarial checker:
  `scripts/eval/check_engram_g14_public_synthetic_protocol_harness.py`;
- pinned shell entrypoint:
  `scripts/check-engram-g14-public-synthetic-protocol-harness.sh`.

The contract pins the preceding G1.4 design-only commit and its exact contract,
validator, and checker hashes. The contract separately pins the fixture bytes.
The implementation independently declares and validates the contract semantics;
it does not reload the registered fixture as its semantic policy.

## Protocol state machine

The only accepted phase order is:

1. development lock;
2. aggregate development feedback;
3. final lock;
4. blinded run plan;
5. synthetic sandbox attestation;
6. deterministic qualification;
7. synthetic run;
8. frozen decision; and
9. mapping reveal.

An out-of-order transition fails closed. A terminal failure is absorbing for a
claimed run ID. The implementation keeps state in memory and deliberately has
no persistence, process, network, database, or runtime integration.

## Candidate locks and feedback

The development lock binds source, configuration, and dependency digests before
feedback. At most two contiguous aggregate-only feedback rounds are admitted.
The final lock adds toolchain/build flags, features/model assets, environment,
sandbox profile, output schema, resource budget, and protocol/runner version.

The final-lock digest is checked again before a run plan is frozen. Feedback
after final lock, a third feedback round, lock replay, and post-lock drift all
fail closed. The fixture contains no source, configuration body, raw probe,
partition material, or candidate-authored scoring input.

## Blinding and release order

Execution and scoring expose only `arm_0` through `arm_4`. The registered JSON
separates `predecision` material from `postdecision_reveal`. The supervisor
removes the reveal, decision aggregates, and expected result before constructing
the scorer view. A synthetic custodian owns those values, computes the frozen
decision only after the final scoring receipt, and releases the mapping only
after the decision receipt. The semantic map is absent from run-plan,
invocation, decision, and mapping-reveal receipt payloads; the public chain
contains only its commitment.

The custodian records the exact scoring-chain head and frozen decision on its
own instance. Reveal revalidates all five ordered successful invocation
receipts, their opaque arms and destroyed-scratch flags, the decision receipt,
and its link to that stored head. A standalone or replayed decision receipt
cannot trigger reveal.

This proves an interface split and protocol order, not process-enforced
evaluator custody or real unblinding. The full public KAT file necessarily
contains its postdecision expected mapping, but the checker captures the actual
scorer-view argument and proves that neither mapping nor semantic arm names
entered it.

## Synthetic sandbox proof interface

The registered profile name is
`nono_landlock_or_seatbelt_deny_by_default_offline_runner_v1`. In this gate it
is only a contract identifier. The input evidence kind is explicitly
`public_synthetic_policy_attestation_not_kernel_enforcement`.

The state machine requires all three independent reports—platform support,
policy application, and active state—and then checks every canary observation.
Allowed canaries are candidate-code read, dependency read, and ephemeral
scratch write. Denied canaries cover repository metadata, private manifest,
live store, network, subprocess, dynamic plugin, non-scratch write, wall clock,
external entropy, extra inherited descriptor, and free-form output.

Support, apply, or active false; a canary mismatch; or a synthetic claim of
native enforcement invalidates the claimed run. Thus `active=true` is not
treated as proof. The result always reports both
`native_sandbox_enforcement_implemented=false` and
`native_sandbox_enforcement_verified=false`.

No OS API is called. A future native adapter must be a separate preregistered
public-synthetic gate with platform-specific executable canaries. It may not
reuse this receipt as evidence that Landlock or Seatbelt actually enforced a
policy.

## Determinism and state isolation

The fixture commits a seed schedule and supplies two qualification replays.
The harness requires byte-identical ranked-output commitments, globally unique
invocation IDs, no qualification/run ID overlap, one invocation per opaque arm,
destroyed scratch, and equal resource-budget markers.

A timeout, crash, missing output, schema failure, scratch survival, resource
drift, duplicate invocation ID, cross-stage ID reuse, or replay divergence
invalidates the entire claimed run. Once a structurally valid synthetic fixture
is admitted, its run ID is consumed before mapping-commitment validation or any
attempt-specific phase. There is no selective retry. A consumed run ID cannot
be reclaimed, whether the run completed or failed.

The state-isolation evidence remains synthetic. No fresh process, mount
namespace, descriptor table, cache, or scratch directory is created here.

## Decision rule

The harness applies the preregistered integer and decimal guards without
post-observation configuration:

- at least two paired primary repairs versus each comparator;
- zero new exact, related, no-relevant-gap, or per-mode intrusion regressions;
- exact and related MRR absolute loss at most `0.05`;
- at most one repair per falsifier versus each comparator; and
- candidate repairs strictly above every falsifier.

FIT/development input cannot decide the final verdict. A synthetic PASS or FAIL
proves only that the arithmetic implementation follows the frozen rule; it is
not an experimental conclusion.

## Receipts and rollback lessons

Every phase appends a closed, synthetic-only event with monotonic sequence,
previous-event hash, embedded closed aggregate payload, recomputed payload
commitment, and event hash. The registered happy path yields 14 events.
Reordering or modifying an event without recomputing its commitments breaks
structural verification. Before scorer execution, the supervisor separately
derives and freezes the exact expected 12-event predecision scoring-chain head
from the validated fixture. The decision/reveal custodian rejects any
self-consistent but fully rehashed alternate chain against that process-local
anchor. The checker also constructs every expected payload and event
independently from the pinned fixture and compares the exact chain head.
Receipts contain only safe aggregate status and commitments; they contain no
raw query, target, corpus, arm mapping, candidate text, path, identity, or
result.

The in-memory hash chain and process-local expected-head anchor are not a
signature or trusted append-only ledger. Their authenticity comes only from the
reviewed Git tree, byte pins, and independent expected-chain check in this
gate. A real runner would need separately reviewed durable anchoring.

Recoverable failures require no human approval. Once a run ID is claimed, a
fault marks it `INVALIDATED_NO_RETRY`. If rollback itself fails, the registry
model emits a synthetic lesson containing only a run commitment and reason
code. The lesson states that a real implementation must persist equivalent
evidence, but this in-memory laboratory does not claim durable storage.

## Human safety audit boundary

Routine public contract validation, unchanged synthetic exercise, fail-closed
denial, and successful automatic rollback do not need human approval. Manual
safety audit remains a transition gate for real/private access or capability
consumption, post-final-lock candidate/runner drift, post-observation rule or
retry changes, unblinding/rerun, sandbox-policy widening, first real runner
enablement, and suspected secret/privacy/identity/corpus/result exposure.

This implements the user's operating rule: reversible work proceeds
autonomously; persistent or high-blast-radius trust transitions do not.

## Run

```bash
scripts/check-engram-g14-public-synthetic-protocol-harness.sh

python3 scripts/eval/engram_g14_public_synthetic_protocol_harness.py \
  validate-contract

python3 scripts/eval/engram_g14_public_synthetic_protocol_harness.py \
  exercise --enable-public-synthetic
```

The shell checker pins all four core artifact hashes, compares deterministic
contract and exercise receipts, proves the default-off path, runs the adversarial
checker with independent contract/fixture schemas, decision arithmetic, receipt
payloads, and chain construction, and rejects runtime-crate leakage.

## Only permitted successor

The only permitted successor is
`separate_public_synthetic_native_sandbox_adapter_preregistration_design_review`.
It is a design review for a default-off native adapter KAT—not permission to
add `nono`, execute candidate code, open a corpus, consume freeze authority, or
run G1.4.
