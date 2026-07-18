# Engram G0 Real-Failure Intake And Baseline Replay

Date: 2026-07-17

Status: **IMPLEMENTED AS READ-ONLY G0 INFRASTRUCTURE; NO REAL FAILURE ADMITTED**

Upstream decision: BioCortex commit `d5ea450` proposed an engram-reorganization hypothesis but correctly
blocked mechanism work until a real application exhibits a precision/generalization failure against its
current strong baseline.

## Decision

Agent-Bridge supplies the first G0 intake and replay package because it already has a real retrieval baseline
and a read-only snapshot-evaluation pattern. G0 does not build or evaluate an engram-inspired candidate. It
answers only:

> Does a consumer-owned, pre-existing failure reproduce as either a generalization gap or an
> overgeneralization gap under the current baseline?

The executable surface is:

- `scripts/eval/engram_g0_failure_intake.py validate-contract` — validates the frozen public contract;
- `scripts/eval/engram_g0_failure_intake.py capture` — reads a private intake spec, copies the live SQLite
  database with the online-backup API, runs FTS/hybrid/semantic retrieval against only the temporary snapshot,
  and emits a redacted packet plus receipt. Every probe/mode observation gets a fresh clone of one frozen base
  snapshot, so baseline access metadata, telemetry, and coactivation writes in a disposable clone cannot
  influence a later observation;
- `scripts/eval/engram_g0_failure_intake.py evaluate` — classifies an already-redacted packet without opening a
  database or calling Agent-Bridge;
- `scripts/check-engram-g0-failure-intake.sh` — deterministic contract, classification, and negative tests.

## Failure Signatures

Every episode group contains exactly three consumer-supplied probes. All probes for one episode remain in the
G0 `fit_only` partition.

| Exact | Related | Unrelated rejects episode | Classification | G0 relevance |
|---:|---:|---:|---|---|
| pass | fail | pass | `generalization_gap` | relevant |
| pass | pass | fail | `overgeneralization_gap` | relevant |
| fail | any | any | `ordinary_retrieval_gap` | not mechanism-specific |
| pass | pass | pass | `no_relevant_gap` | no application gap |
| pass | fail | fail | `ambiguous_dual_failure` | not admissible |

“Pass” uses the best rank across the frozen FTS, hybrid, and semantic modes at top 10. The unrelated probe
passes only when none of the episode's accepted target keys appears in the top 10 of any mode.

## Privacy And Isolation

A real private intake spec contains raw queries and accepted target keys. It must:

- live under the repository's ignored, untracked `data/` tree;
- be consumer-owned and reviewed;
- describe a failure observed before this candidate direction was selected;
- contain no candidate-authored probes;
- carry source and reviewer receipt hashes plus rights clearance.

`capture` refuses a real spec outside that boundary. It copies the exact baseline executable once, verifies its
binary hash and source commit, opens the source database through SQLite's read-only online-backup path, and
creates one frozen base snapshot. Every probe/mode observation gets a fresh disposable clone and uses the same
frozen executable. It labels retrieval as `eval`, disables outcome collection, and forces
`AB_BIOCORTEX_RETRIEVAL_DISABLE=1`. Before each observation it hashes the clone and requires byte identity with
the frozen base. It fails if a child does not confirm its clone path, the frozen base changes, or any observation
changes durable memory content, edges, schema, or the logical FTS key/content projection. Audited observation
clones are removed immediately to keep temporary disk use bounded.

The current baseline itself can write query telemetry, coactivation, and—during hybrid graph reads—
`access_count`/`last_accessed_at` into the disposable clone. Those access fields can influence a later ranking,
so they are explicitly excluded from the durable-content fingerprint but never from the isolation boundary:
the clone is used for exactly one probe/mode observation, never reused, and deleted with the temporary
directory. Their legacy update trigger can also rewrite equivalent FTS5 shadow segments, so the gate compares
the logical key/content projection rather than internal segment layout. No child receives the live database
path.

The emitted packet and receipt contain hashes, ranks, bounded machine labels, and classifications only. Raw
queries, memory keys, retrieved records, database paths, and stderr are not emitted.

The baseline receipt also binds a fixed allowlist of retrieval-relevant environment variables by one canonical
SHA-256 without emitting their values. Delegated embedding is accepted only through a credential-free loopback
URL, so private probes cannot be sent to an external host. If the seed/perception-filter reranker is active,
`capture` reads its sidecar state through a bounded stable file descriptor, records only its hash, copies the
exact bytes into the temporary directory, and points every child at that frozen copy. An absent or explicitly
disabled sidecar is also frozen as an effective disabled state. This prevents a concurrently refreshed sidecar
from changing ranks between observations.

## Admission Boundary

The public synthetic fixture covers all four primary classifications but always returns
`SYNTHETIC_ONLY_NO_ADMISSION`. Relabelling synthetic evidence as real without valid provenance returns
`BLOCKED_PROVENANCE`.

A genuine `PASS_OBSERVED_RELEVANT_FAILURE` means only:

```text
ready_for_g1_grouped_corpus_design = true
```

It still fixes all of the following to false:

```text
candidate_implementation_authority
g1_corpus_freeze_authority
retrieval_order_mutation_authority
runtime_promotion_authority
```

Real G0 intake accepts at most three episode groups and 32 accepted target keys per episode, preventing this
intake tool from quietly becoming a corpus evaluator. Synthetic input is capped at four groups; the public
fixture uses those four solely to cover every primary classification. G1 must independently choose corpus size,
episode-level FIT/DEV/sealed splits, metrics, budgets, and reviewer custody. G0's minimum of one real relevant
group is an observed-failure receipt, not a scientific sample-size claim.

## Commands

Validate the public contract and synthetic controls:

```bash
scripts/check-engram-g0-failure-intake.sh
```

Load the same non-secret machine retrieval profile used by the current runtime, then create the hash-only
environment receipt. Copy its environment hash and embedding transport into the reviewed private spec; capture
will fail if either drifts:

```bash
source "$HOME/.config/agent-bridge/machine.env"
python3 scripts/eval/engram_g0_failure_intake.py fingerprint-environment \
  --contract scripts/eval/fixtures/engram_g0_failure_intake_contract_v0.json \
  --pretty
```

Evaluate a redacted packet:

```bash
python3 scripts/eval/engram_g0_failure_intake.py evaluate \
  --contract scripts/eval/fixtures/engram_g0_failure_intake_contract_v0.json \
  --packet data/eval/engram-g0/<incident>/replay.packet.json \
  --require-g1-ready
```

Replay a reviewed private incident against a disposable snapshot:

```bash
python3 scripts/eval/engram_g0_failure_intake.py capture \
  --contract scripts/eval/fixtures/engram_g0_failure_intake_contract_v0.json \
  --private-spec data/eval/engram-g0/<incident>/private-intake.json \
  --source-db /path/to/state.db \
  --agent-bridge-bin /path/to/version-bound/agent-bridge.real \
  --repo "$PWD"
```

Run `capture` in the same shell as `fingerprint-environment`. On this node the machine profile selects the
already-running localhost embedding service; omitting the profile would be a different baseline and is rejected
by the private spec's environment binding.

Do not redirect a real receipt into tracked source. Keep the incident packet under ignored `data/` until G1
defines its custody and disclosure policy.

## Non-Claims

- No real failure has been captured or admitted by this implementation.
- The packet's consumer/provenance fields remain externally reviewed assertions; schema validation is not a
  semantic oracle or signature authority.
- G0 does not prove that engram reorganization will help, does not create paraphrases, and does not select a
  candidate mechanism.
- G0 does not alter memory, ranking, retrieval configuration, deployment, or live runtime behavior.
