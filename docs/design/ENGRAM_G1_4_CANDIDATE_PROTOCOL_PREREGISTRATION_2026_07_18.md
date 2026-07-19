# Engram G1.4 Candidate Protocol Preregistration

Date: 2026-07-18

Status: **DESIGN PREREGISTERED / PUBLIC SYNTHETIC HARNESS PENDING / NO DATA OR EXECUTION AUTHORITY**

## Decision

This gate freezes the candidate-development, blinding, sandbox, run-lifecycle,
decision, and receipt contract for the later G1.4 experiment. It does not
implement a candidate or protocol runner, open any corpus partition, consume a
real freeze capability, execute BioCortex, mutate retrieval, write the live
store, unblind results, or promote runtime behavior.

The registered public contract is
`scripts/eval/fixtures/engram_g14_candidate_protocol_preregistration_contract_v0.json`,
SHA-256
`dca8ac03fbc915d70c6470492136ca9e554722aeed8d789e85714ece7e60ea41`.
Its pure structural validator SHA-256 is
`9e03d53b19eb9dd273ac6dc49cde7a9a93221de50be58eede37d25729374cd1c`;
the adversarial checker SHA-256 is
`49d3734eb52a73235cc858e7ae43d0de99999eb0f693f76661375e22683c5a92`.

The checker digest is an out-of-band review and Git-tree identity. The checker
pins the contract and validator upstream; the reviewed commit pins the checker
downstream. A checker cannot contain its own digest without a circular hash
dependency.

A valid receipt has exactly one positive **boundary bit**:
`g1_4_design_preregistered=true`. Other positive values describe frozen future
requirements, not present capabilities. Every access, implementation, execution,
unblinding, mutation, write, and promotion authority remains false. The only
permitted successor is a separate, default-off, public-synthetic protocol-
harness implementation gate.

## Immutable predecessor chain

The contract pins synthetic isolated-lab predecessor commit
`bdd0b07b5e9afcc20d030e7e3dcfd404d44e8d54` and its exact contract,
implementation, Python checker, and shell entrypoint hashes. It also binds the
adapter-preregistration and G1.3 contract, validator, and checker hashes.

The validator re-hashes all ten public artifacts on every successful run. The
predecessor remains synthetic and grants no real authority. This design cannot
launder it into a real freeze capability.

## Frozen experiment

The decisive question remains whether `clustered_reorganization` reduces
unrelated-target intrusion without materially degrading exact or related
retrieval. The arms are fixed before observation:

- candidate: `clustered_reorganization`;
- comparators: `stable_control`, then `density_only`;
- mechanism falsifiers: `mechanism_off`, then `cluster_shuffled`;
- retrieval modes: FTS, hybrid, and semantic at top 10.

The paired episode group is the decisive unit and sealed data is the decisive
partition. FIT, development, and sealed results cannot be pooled. Rates are
diagnostics, not decision authority.

The inherited 30-group corpus remains fixed at FIT 12, development 8, sealed
10, with three probe classes per group. It preserves the registered stratum,
family-cap, primary-group, and G0 FIT-only admission rules. The candidate may
not change group membership, partitioning, expected targets, or scoring.

## Candidate lock and development budget

Candidate evolution uses a two-phase artifact lock:

1. a development lock is required before aggregate development feedback; and
2. a final sealed lock is required before any sealed access.

At most two reviewer-mediated, preregistered aggregate development-feedback
rounds are allowed. The final lock binds source, configuration, dependency
lock, toolchain/build flags, feature flags/model assets, environment allowlist,
sandbox profile, output schema, resource budget, protocol contract, and runner
version. Any later source, configuration, dependency, or policy change requires
a new protocol revision; the candidate cannot approve itself.

Candidate authors may use FIT but cannot see raw development or sealed probes,
partition membership outside FIT, manifest paths, group identifiers, expected
targets, or arm mapping. A custodian delivers one bounded probe through an
evaluator-owned pipe. Independent scoring uses opaque arm identifiers; the
mapping is revealed only after an append-only decision receipt is frozen.

## Nono, Landlock, and Seatbelt boundary

The design follows the useful shape in grok-build's `xai-grok-sandbox` at
reference commit `8adf9013a0929e5c7f1d4e849492d2387837a28d`: apply an
irreversible OS policy before untrusted work, describe capabilities rather than
individual prompts, pin the `nono` dependency when rule ordering matters, keep
platform-specific deny tests, and report whether enforcement actually became
active.

G1.4 deliberately does **not** inherit several grok-build product tradeoffs:

- unsupported kernels or policy-application errors may not continue
  unsandboxed;
- an `is_active` flag is not sufficient evidence that every required denial
  works;
- candidate network access cannot remain open for an LLM API;
- subprocess restriction cannot be Linux-only child seccomp; and
- workspace or user configuration cannot widen the registered profile.

The future profile
`nono_landlock_or_seatbelt_deny_by_default_offline_runner_v1` is therefore a
contract name, not a claim that `nono` alone supplies every control. The
platform adapter must combine filesystem confinement with whatever native
mechanism is required to deny network, process spawn, dynamic plugin loading,
and external entropy on that OS. Unsupported or semantically incomplete
platforms fail closed.

Before any candidate bytes are loaded, a fresh supervisor must:

- clear inherited descriptors except fixed evaluator input/output channels;
- install an explicit environment allowlist and fixed working directory;
- expose candidate code and dependencies read-only;
- expose exactly one empty ephemeral scratch directory as writable;
- hide repository metadata, the live store, private manifests, and partition
  paths;
- deny network, subprocesses, plugin loading, wall clock, and unregistered
  randomness; and
- enforce equal CPU, memory, time, file-count, byte, mount, and cache policy
  across arms.

Each future platform adapter needs executable positive and negative canaries:
allowed code/dependency reads and scratch writes must succeed, while repository,
manifest, live-store, network, subprocess, plugin, forbidden-write, clock, and
entropy probes must fail. A missing, skipped, or unexpectedly passing canary
invalidates the run. This design gate implements none of those mechanisms.

Candidate stdout, stderr, and free-form logs are not released. Output has a
fixed schema, cardinality, and byte ceiling and may not contain candidate-
authored text. These controls limit both accidental disclosure and covert
channels; redaction review remains mandatory before result release.

## Determinism and run lifecycle

The future runner uses a registered seed schedule hidden from the candidate for
sealed evaluation. Two identical FIT qualification replays must produce
identical ranked outputs. Every arm/group invocation starts in a fresh process
with fresh scratch; cross-arm, cross-group, and cross-partition state is
forbidden.

A real run requires a real single-use authenticated freeze capability bound to
repository, scope, manifest, protocol, runner, sandbox, resources, and final
candidate lock. It is consumed atomically before the private run plan opens.
The synthetic predecessor capability is never accepted as real authority.

Sealed execution is one-shot. A timeout, crash, schema failure,
nondeterminism, sandbox drift, or infrastructure fault invalidates the entire
sealed run. Selective retry and partial rerun are forbidden. Any rerun requires
a new protocol revision, a fresh capability, and manual safety audit; partial
or intermediate sealed results remain closed.

## Frozen decision rule

The candidate must repair at least two paired primary sealed groups versus
each comparator, with zero new exact misses, related misses, no-relevant-gap
regressions, or per-mode unrelated-intrusion increases. Exact and related MRR
absolute loss may not exceed `0.05`.

Each mechanism falsifier may repair at most one primary group versus each
comparator, and the candidate must outperform each falsifier. All guards apply
simultaneously. Missing, timeout, crash, or schema-invalid invocation counts as
failure. No threshold, arm, metric, resource, missingness, or retry rule may be
changed after observation.

## Receipts and privacy

The future protocol requires hash-chained, append-only artifact-lock, blinded-
run-plan, per-invocation, and decision receipts. They bind the contract,
candidate, runner, sandbox, resources, predecessor, monotonic sequence, nonce,
and trusted time.

Public receipts cannot contain raw query, target, manifest, group, family,
partition, identity, or candidate-authored text. Public and private digest
namespaces are disjoint; low-entropy private values use salted commitments and
small aggregate counts are suppressed. The present validator emits only a
deterministic public design receipt.

## Human-audit policy

Routine public contract validation, an unchanged public-synthetic harness run,
and fail-closed denial need no human approval. Reversible failures roll back
automatically. A rollback failure or residual state must leave durable evidence
and a durable lesson before retry.

Manual safety audit is a transition gate only for:

- first real freeze-capability consumption or private run-plan opening;
- candidate/runner source, dependency, toolchain, configuration, or policy
  change after final lock;
- FIT, development, sealed, or partition-access widening;
- metric, threshold, arm, resource, retry, or missingness-policy changes after
  observation;
- sealed unblinding, selective retry, or rerun;
- sandbox filesystem, network, subprocess, log, output, or side-channel policy
  changes;
- first real protocol-runner enablement; or
- suspected secret, privacy, identity, corpus, or result exposure.

The structural validator cannot infer or fabricate an audit outcome. This
keeps recoverable engineering autonomous without turning persistent trust and
privacy transitions into silent defaults.

## Threat model

The contract registers 16 threats: predecessor-capability laundering;
candidate/runner drift; arm substitution; corpus or target leakage; network,
subprocess, plugin, or filesystem exfiltration; output/timing/resource covert
channels; cross-invocation state; nondeterminism; adaptive development;
selective retry; post-observation policy drift; partition pooling or peeking;
resource/cache asymmetry; candidate-authored targets/scoring/receipts; receipt
privacy or digest aliasing; and cross-stage/scope/repository replay.

Every control is a future requirement with current status
`unimplemented_fail_closed`. Passing this gate proves only that the design is
exactly preregistered and has not drifted.

## Run

```bash
scripts/check-engram-g14-candidate-protocol-preregistration.sh

python3 \
  scripts/eval/engram_g14_candidate_protocol_preregistration.py \
  validate-contract \
  --contract \
  scripts/eval/fixtures/engram_g14_candidate_protocol_preregistration_contract_v0.json
```

The checker pins raw contract and validator hashes, validates all ten public
predecessor artifacts, compares deterministic receipts, and drives 660
recursive semantic mutations through a pure policy seam whose section rules
are declared in validator code independently of the JSON fixture. It
also rejects byte drift, duplicate JSON keys, symlinks, non-snake-case fields,
duplicate threat/audit entries, forbidden imports, and runtime-crate leakage.
A hardlink of this public contract is intentionally accepted and still emits
zero execution/data authority; no private-file custody claim is made.
