# Engram G1.1 Freeze Preflight

Date: 2026-07-18

Status: **READY FOR INDEPENDENT ROLE ASSIGNMENT**

## Decision

G1.1 preserves the G1 v0 design bytes and adds a successor preflight before
any new corpus observation. The successor removes rate-granularity and custody
ambiguities, defines hash-only private packet structures, and keeps every
freeze, implementation, experiment, retrieval, write, and promotion authority
false.

The registered contract is
`scripts/eval/fixtures/engram_g1_freeze_preflight_contract_v1.json`, SHA-256
`5d4835fa2aa404224b98e7a60574121118051d771079f5a0422ab5839564e94a`.
It binds the immutable G1 v0 design at commit
`d8a17461858354a1b0bbd4f86c29eae75bdf0aa9`, SHA-256
`275ae840b62a8a5408ea11e98836aefded998d87d2a2c4846939414a3128a0f0`.

## Why v1 is needed

The v0 rate gates were directionally correct but underspecified at the sealed
sample size:

- five primary sealed groups make a 0.20 absolute reduction exactly one group;
- a 0.02 hit-rate loss budget means zero tolerable losses at the registered
  group counts;
- “strongest baseline” did not distinguish the application retrieval baseline
  from the later mechanism comparators;
- 35% of 30 groups needs an explicit integer rule;
- role names were defined, but their private commitments and manifest binding
  were not yet machine-checkable.

No new consumer material was examined to make this amendment. V0 remains an
auditable predecessor; v1 supersedes only its decisive-rate interpretation.

## Discrete decision rule

The application baseline remains the frozen Agent-Bridge
FTS/hybrid/semantic any-mode envelope. Its only purpose in G1 is to classify
each episode as an exact, related, and unrelated retrieval signature.

The later offline experiment has a different comparison:

- candidate: `clustered_reorganization`;
- comparators: `stable_control` and `density_only`;
- decisive unit: one sealed episode group;
- primary stratum: `overgeneralization_gap`;
- candidate must repair at least two paired primary groups versus **each**
  comparator;
- no new exact miss, related miss, no-gap regression, or per-mode unrelated
  intrusion is permitted;
- exact and related MRR absolute loss remains capped at 0.05;
- `mechanism_off` and `cluster_shuffled` must eliminate the claimed advantage.

Rates remain reportable diagnostics but cannot decide the gate. Even a pass is
only a deterministic engineering screen; it has no population-effect,
neuroscience-equivalence, product-value, or runtime authority.

## Frozen corpus arithmetic

The scored corpus remains 30 groups: FIT 12, development 8, sealed 10. It must
contain at least 15 overgeneralization, 9 no-gap, and exactly 3 ordinary-
retrieval exclusion controls with the preregistered partition minima. Up to
three generalization-gap or additional eligible groups may fill the remaining
slots.

The 35% family cap is now `floor(0.35 × 30) = 10` groups. At least four
independent application families are required. The G0 incident is bound by
hash, appears exactly once, remains an overgeneralization case, and may appear
only in FIT.

Two identical baseline replays produce exactly 540 frozen-manifest
observations. The 36-group intake ceiling remains 648 observations across two
replays, but alternates cannot enter the frozen manifest.

## Private role packet

Actual role packets use schema
`agent_bridge.engram_g1_role_commitment_packet.v1` and remain ignored under
`data/`. They contain no names or contact details. A holder is represented by:

```json
{
  "role": "freeze_reviewer",
  "independence_class": "independent_reviewer",
  "holder_commitment_sha256": "<private salted commitment>",
  "appointment_receipt_sha256": "<private appointment receipt commitment>"
}
```

The packet must contain one candidate implementer, one consumer curator, two
freeze reviewers, and one sealed evaluator/custodian. All five holder
commitments and appointment receipts must be distinct. The candidate may not
curate, approve freeze, read the private manifest, or hold sealed custody.

Holder commitments require private salts. A plain hash of a name, account, or
session identifier is not admissible; the salts remain with the custodian and
never enter a redacted receipt.

The validator checks structure and separation claims. It explicitly does not
authenticate a person, an appointment, independence, or receipt truth. A real
packet can only become ready for independent role-commitment review; it grants
no assembly authority.

## Private corpus manifest

Actual manifests use schema
`agent_bridge.engram_g1_private_corpus_manifest.v1` and also remain ignored
under `data/`. Each episode group stores commitments and ranks, never raw
queries or memory keys:

```json
{
  "episode_group_id_sha256": "<commitment>",
  "application_family_id_sha256": "<commitment>",
  "partition": "sealed",
  "declared_signature": "overgeneralization_gap",
  "expected_target_set_sha256": "<commitment>",
  "probes": [
    {
      "probe_class": "unrelated",
      "query_sha256": "<commitment>",
      "expected_target_set_sha256": "<same group commitment>",
      "replay_ranks": [
        {"fts": 0, "hybrid": 0, "semantic": 3},
        {"fts": 0, "hybrid": 0, "semantic": 3}
      ]
    }
  ]
}
```

The manifest binds the exact role-packet bytes, frozen baseline identity,
source/rights/consumer-observation receipts, replay-integrity hashes, and all
30 indivisible episode groups. Its redacted receipt reports only aggregate
counts; it emits no group, query, target, family, partition-membership, or role
commitments.

The manifest also records an assembly timestamp later than the bound role
packet timestamp. Equal or reversed timestamps fail closed, so “appoint first,
curate second” is checked rather than accepted only as prose.

Group, family, query, source, and target commitments likewise require private
custodian-held salts. “Hash-only” is a structural minimization rule, not a
claim that an unsalted hash safely anonymizes guessable material.

A structurally valid real manifest can become ready for independent
corpus-freeze **review**. The preflight validator cannot approve that review or
issue a freeze receipt.

## Fail-closed boundary

Run:

```bash
scripts/check-engram-g1-freeze-preflight.sh

python3 scripts/eval/engram_g1_freeze_preflight.py validate-contract \
  --contract scripts/eval/fixtures/engram_g1_freeze_preflight_contract_v1.json

python3 scripts/eval/engram_g1_freeze_preflight.py validate-role \
  --contract scripts/eval/fixtures/engram_g1_freeze_preflight_contract_v1.json \
  --role-packet data/eval/engram-g1/ROLE_PACKET.private.json

python3 scripts/eval/engram_g1_freeze_preflight.py validate-manifest \
  --contract scripts/eval/fixtures/engram_g1_freeze_preflight_contract_v1.json \
  --role-packet data/eval/engram-g1/ROLE_PACKET.private.json \
  --manifest data/eval/engram-g1/CORPUS_MANIFEST.private.json
```

The checker builds a complete 30-group synthetic manifest in a temporary
directory and rejects relaxed decision rules, duplicate role holders, false
role classes, candidate access, real packets outside ignored `data/`, wrong
group counts, role-binding or chronology drift, G0 leakage into sealed, replay drift,
application-family dominance, signature drift, candidate-authored probes, raw
queries, duplicate query commitments, insufficient sealed-primary groups,
unsalted commitments, assembly-attestation drift, and duplicate JSON fields.

No real role packet or corpus manifest is created by this slice. The next
external action is to appoint and independently review the five role holders.
A separately registered role-commitment review may then authorize private
assembly. Only a still-later corpus-freeze review may authorize freezing the
assembled manifest.
