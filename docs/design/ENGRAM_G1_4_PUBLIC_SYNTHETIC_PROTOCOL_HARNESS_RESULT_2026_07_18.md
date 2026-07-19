# Engram G1.4 Public-Synthetic Protocol Harness Result

Date: 2026-07-18

Verdict: **PASS — PUBLIC SYNTHETIC PROTOCOL ONLY / DEFAULT OFF / NO NATIVE SANDBOX OR EXPERIMENT AUTHORITY**

## Delivered

- closed public-synthetic implementation contract and immutable KAT fixture;
- standard-library-only in-memory protocol state machine;
- two-phase candidate-lock and two-round feedback model;
- opaque-arm plan, decision-before-reveal ordering, and mapping commitment;
- synthetic support/apply/active plus 14-canary sandbox proof interface;
- split scorer view and synthetic postdecision custodian material;
- deterministic replay and globally unique invocation-ID checks;
- one-shot run registry with whole-run invalidation and no retry;
- fixed candidate/comparator/falsifier decision arithmetic;
- predecision-frozen scoring-chain head plus 14-event append-only hash chain;
- rollback-failure lesson model; and
- pinned shell entrypoint, adversarial checker, design note, and eval index.

No runtime crate changed. No process, native sandbox, candidate, corpus,
capability, database, retrieval path, live store, MCP tool, deployment, or
result-release surface was touched.

## Test-first evidence

The first shell-checker run was intentionally red before the implementation and
checker existed. It failed with `FileNotFoundError` for
`scripts/eval/engram_g14_public_synthetic_protocol_harness.py`. No persistent
state had been created.

The first positive exercise then failed closed because one synthetic dependency
digest had 63 hexadecimal characters. The fixture was corrected to a strict
64-character SHA-256 and both fixture and contract byte pins were recomputed;
the validator was not weakened.

Adversarial design exposed a more important lifecycle defect: dynamic sandbox,
determinism, and invocation outcomes were initially forced to success during
shape validation, before the one-shot run ID was claimed. Those fields were
changed to closed types/enums at the boundary and enforced inside the claimed
run. A sandbox or invocation fault now produces `INVALIDATED_NO_RETRY`, and a
second attempt with the same registry fails with `E_RUN_REPLAY`.

The first independent read-only review then found four material evidence gaps:
payload hashes were not tied back to embedded payloads; the checker delegated
too much arithmetic and chain verification to the implementation; a mapping-
commitment fault occurred before run-ID consumption; and the scorer-facing path
received a fixture containing postdecision mapping material. The implementation
now embeds and re-hashes every closed payload, consumes the run ID before any
attempt-specific validation, and splits scorer input from a synthetic decision/
reveal custodian. The checker independently declares the relevant schemas,
decision arithmetic, exact 14 payloads, event hashes, and expected chain head.
It also captures the scorer view and proves that the mapping, decision input,
expected result, and semantic arm names are absent. A rollback-failure injection
now passes through the harness invalidation path and emits the minimal lesson.

The second read-only review found one remaining interface hole: a caller could
invoke custodian reveal with a standalone syntactically valid decision receipt,
without first asking that custodian to freeze a decision over five invocations.
The custodian now stores its own scoring-chain head, decision, and reason count;
reveal revalidates the five ordered invocation receipts and their success/
scratch flags, the decision payload, and the chain link. The checker covers
standalone-decision forgery, decision replay, valid reveal, and reveal replay.

The third focused review found that a structurally valid chain whose payloads
and every subsequent hash were recomputed could still pass the custodian's
self-consistency checks. The supervisor now derives and freezes the exact
12-event predecision scoring-chain head before scorer execution. The custodian
requires that process-local trust anchor both before freezing a decision and
before revealing the map, while the checker independently constructs the same
expected chain and proves that a fully rehashed alternate chain is rejected
with `E_RECEIPT_ANCHOR`. A final focused read-only review returned `PASS`.

## Current evidence

The adversarial checker, including its implementation-independent schema,
decision, payload, and hash-chain oracles, currently proves:

- 489 contract field/type/value/order mutations are rejected by semantic rules
  declared independently of the JSON contract;
- raw contract and fixture byte drift fail separate SHA-256 pins;
- duplicate JSON keys, floats, non-standard numbers, invalid UTF-8, and a
  non-object root fail closed;
- 14 claimed-run fault classes—including pre-run mapping-commitment drift—
  invalidate the entire run and prohibit retry;
- all eight decision-guard families reject their registered counterexample;
- the exact `0.05` MRR-loss boundary remains accepted;
- lock replay, third feedback, post-final-lock feedback, final-lock drift,
  out-of-order phases, early reveal, and terminal replay fail closed;
- two successful exercises produce byte-identical receipts and chain heads;
- embedded-payload drift and receipt reorder/tamper fail; a fully rehashed
  alternate chain is rejected by the predecision-frozen runtime anchor and
  differs from the independently expected checker chain and head;
- semantic arm names enter neither scorer input nor receipts;
- successful and invalidated run IDs are both one-shot;
- rollback failure through the main harness emits a minimal synthetic lesson
  without raw run material;
- the CLI is default-off and accepts no candidate/private/capability path;
- forbidden native-sandbox, network, process, database, and escape imports are
  absent; and
- no harness symbol appears under `crates/`.

The registered happy path emits
`PASS_PUBLIC_SYNTHETIC_PROTOCOL_HARNESS_NO_AUTHORITY`, 14 canary checks, 14
receipt events, and false values for every native enforcement, real candidate,
real capability, private corpus, sealed execution, G1.4 opening, release,
retrieval mutation, live write, runtime promotion, and production-admissibility
field.

The final core byte pins are:

- implementation: `52cc851419880f93d8585fee1a4378788564bbcadbeb84161d4e40e67c51ed05`;
- checker: `bc896b9d284cc644be965dcb7fa20ea80ff5629783922ce7b54bfedd3ed9df10`;
- contract: `6fae57e239594978810d03d2aee33133d3af8439527dd6aadef6884d5bba1b9d`;
- fixture: `477cf9b326f52fc3f8ce9138346bb55e2692e5b473ac5f0c5d9b24e457350607`.

The complete predecessor chain was rerun after the final review correction:
G0 failure intake, G1 corpus design, freeze preflight, role review, corpus
freeze review, authenticated-authority preregistration, the 259-check isolated
lab, the 660-mutation G1.4 preregistration checker, and this 489-mutation
harness checker all passed. Black, `py_compile`, Pyflakes, both JSON parsers,
`bash -n`, `git diff --check`, and the no-runtime-symbol scan also passed.

## Nono conclusion

This result validates the protocol boundary around a future nono-based adapter,
not nono itself. The useful adopted shape is: fail closed when unsupported,
separate support/apply/active evidence, prove every allow/deny capability with
an executable canary, bind environment/mount/output/resources, and invalidate
the whole run on drift.

Native Seatbelt/Landlock enforcement remains completely unimplemented and
unverified. It cannot become true through a synthetic receipt or an `active`
flag.

## Human-audit policy

No manual approval was needed: all work was isolated, reversible, public,
synthetic, and runtime-disconnected. Automatic rollback is the default. A
rollback failure must leave durable evidence and a durable lesson before a
real retry. Manual safety audit remains reserved for persistent or high-blast-
radius transitions such as private access, real capability use, policy
widening, post-lock/post-observation change, real runner enablement, rerun or
unblinding, and suspected exposure.

## Authority boundary and next gate

G1.4 remains closed. This PASS does not authorize candidate implementation,
private data access, native sandbox execution, sealed evaluation, unblinding,
retrieval/runtime change, deployment, or promotion.

The only permitted next action is a separate default-off
`separate_public_synthetic_native_sandbox_adapter_preregistration_design_review`.
That review may freeze the KAT interface for Darwin Seatbelt and Linux
Landlock/nono adapters, but may not yet implement or execute them.
