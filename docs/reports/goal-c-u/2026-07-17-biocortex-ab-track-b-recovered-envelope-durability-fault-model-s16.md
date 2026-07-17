# BioCortex / Agent-Bridge Track B S16 report

Date: 2026-07-17
Outcome: `BLOCKED_FAIL_CLOSED`

## Result

S16 preregisters a deterministic synthetic durability fault model against the
private S15 recovered-envelope adapter lifecycle. Its frozen catalog contains
5,639 rows spanning modeled object, durability-receipt, restart, replica,
generation, and witness states. Twenty S16 tests exercise the catalog and its
fail-closed invariants.

This is a model, not a durable implementation. It adds no production or
provider concrete transport, filesystem, network, database, provider SDK,
credential, production permit, Bridge or `StateStore` caller, deployment,
currentness, admission, or side effect. The three ledgers remain separately
empty: external durability observations: **0**; provider observations: **0**;
owned-lab observations: **0**.

## Modeled durability boundary

The model explicitly separates volatile bytes from bytes labeled durable by a
synthetic schedule. A crash discards volatile state; restart sees only modeled
durable object, receipt, and witness state. Object presence does not imply
receipt presence, acknowledgement does not imply commit, and adapter
completion does not imply downstream currentness or consumption.

Rows cover partial/torn bytes, post-persistence corruption,
object/durability-receipt/witness publication reordering, acknowledgement before commit, commit
followed by response loss, crash at open/data/completion cuts,
object/receipt asymmetry, old snapshots and generations, same-revision
equivocation, stale replicas, split brain, and unavailable or conflicting
witnesses.

Every ambiguous or unsupported state fails closed. There is no hidden retry,
cache, latest selection, replica fallback, byte repair, or best-effort success.
The 5,639 rows are deterministic conformance cases; they are neither sampled
production traffic nor evidence about a real storage system.

The catalog builders construct only raw durable, volatile,
evidence-boundary, and lifecycle facts. A single evaluator derives every
disposition, reason, S15 execution result, and mapped failure; the row builder
cannot accept or override those outcomes. Case labels and expected catalog
rows therefore do not serve as a second result oracle. Exact lifecycle tuples
must also match their durable image; inconsistent pairings fall through to
the unclassified fail-closed result.

The D05 execution boundary is narrower than its 106 modeled rows. A test-only
synthetic `ModelTransport` executes 50 injected failures (`AFTER_OPEN` and 49
data cuts) and 50 exact rereads through newly constructed instances. The six
rows for `BEFORE_OPEN`, `AFTER_COMPLETE_BEFORE_S14`, and `AFTER_HISTORICAL`
remain model-only. No OS process crash or external durable restart is executed,
and the test-only transport contributes zero observations to every external
evidence ledger.

## Unchanged historical chain

The model uses the S15 state surface without replacing the S14 decoder or the
S13/S12 verification chain. Frozen predecessor known answers remain:

- source record R: 5,494 bytes,
  `a788ec43fefa76e393d77c86bbfabeef7d2ae8c5499bb834c1945af5cbb1b3cd`;
- S13 envelope:
  `5d74c7a300abe503b9a79c796394faa23de0c64f22fb80902294fa0654ee15d9`;
- S12 historical chain:
  `afb8aa4945f0e491937f75233c621d52f1bcc1307e6d497352fd9d0fc79b7204`;
- S14 sourced historical chain:
  `d29da2a081b09b2b124298eae40b15ada555196cc5e3fd52d8e4dfadf3f2149b`;
- S15 exact-lookup commitment:
  `866e016ce631433e3e272d0858906f3c76c67204cd74b73ab11b7353e57eae00`.

The finalized independent checker binds the S16 catalog message to 225,852
bytes and SHA-256
`c09cdc640957594cc7acc2eeea39cb4e59993631ef04a1fa1e26a69c285af853`.

## Frozen predecessor handling

S16 adds only one exact feature-gated child-module declaration to the S15
adapter module. It adds no test-fixture seam, makes no production predecessor
item public, and adds no production constructor or caller.

Because that seam changes the S15 packet, this report does not claim that the
current S16 HEAD passes the S15 historical-descendant gate. The S16 gate must
check the exact allowed glue and independently replay the frozen S15 integrated
gate at `80fdb9b5d5f4be5f9663f30cd686cd5fb6bdfd35`. The S16 successor gate then
becomes authoritative for the current tree.

## Verification boundary

The independent checker validates duplicate-free, root-closed contract JSON;
the exact S16-to-S15 feature edge; exact predecessor glue; deterministic row
count and catalog commitment; event/fault/state/observation taxonomies; known
predecessor commitments; and absence of production or Bridge wiring. Its
receipt must byte-match the frozen expected TSV in two isolated passes.

The low-memory gate requires these non-ignored Rust counts:

- S16: 20;
- S15: 13;
- S14: 24;
- S13: 15;
- S12: 32;
- S11: 30;
- S10: 15;
- S9: 15.

It also requires feature-on/off `ab-store` and feature-off `ab-bridge` checks.
Cargo is serial, offline, non-incremental, and built without debug information.
A pass demonstrates local synthetic-model conformance only; it does not
increase the external durability observation count.

## Authorization and evidence boundary

No modeled outcome proves filesystem or database ordering, provider
linearizability, real crash recovery, rollback resistance, non-equivocation,
split-brain fencing, witness independence, owner-authorized selection, capture
attestation, signer custody or separation, runtime S10 delivery, currentness at
use, atomic consume-and-action, exactly once, or admission.

Repeated successful rows remain repeatable historical verification. Modeled
durable bytes are not externally durable bytes, and a modeled witness is not
an independently operated witness. Side effects unlocked: `NONE`.

## Successor boundary

A production-facing successor remains blocked pending a separately authorized
provider or owned-lab evidence plan. Such a plan must map real observations to
the frozen S16 taxonomy, record crash/restart and rollback evidence, and keep
observed and simulated ledgers disjoint. Production permits, capture/custody
and signer-separation evidence, runtime S10 delivery, and atomic
currentness-at-use remain independently required.

## Artifact binding

- catalog_message_len: `225852`
- catalog_sha256: `c09cdc640957594cc7acc2eeea39cb4e59993631ef04a1fa1e26a69c285af853`
- `crates/store/Cargo.toml`: `26c850a68efcbb9f68c9f457251750cae4aaeaa7ae7c0bcdb068790bc808c04a`
- `crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter.rs`: `345666428a6b3d36bfac3258ea69bbdf7262341ac434b7611e7c52fa69af9b14`
- `crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model.rs`: `b10984e6336c436a0b84548d0f8c9f7ad4537df7b491d4863e1b6545f517f2d1`
- `docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_DURABILITY_FAULT_MODEL_S16_2026_07_17.md`: `5333c844fdc24d6f63e5dc1c575765912168dc7b8f9ffafff8b0a7cd9d6c7275`
- `docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-durability-fault-model-s16-v0.json`: `2500ae0651025434392b87d5a151487faa4b6e60a6523e083c1987446c3bdb66`
- `docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s16-v0.json`: `175b58589dbdb0c22310c41451271c822532945d85c25c8f268f5a9b2ac7f7c3`
- `scripts/check-memory-temporal-recovered-envelope-durability-fault-model-s16.sh`: `207f4d3d98f7152efe37645a78e66cd8afc3ed6983f412d15c206129b60b5007`
- `scripts/eval/check_memory_temporal_recovered_envelope_durability_fault_model_s16.py`: `0f4c5d9fb2a63f3a65d56a462a6299819e539a4b5f205610ac1c0daffc8dc0e8`
- `scripts/eval/fixtures/memory_temporal_recovered_envelope_durability_fault_model_s16.expected.v0.tsv`: `875ef3ce65ac06228f4a76de069a34eb79ffa04e805a296369c634fd9a666015`
