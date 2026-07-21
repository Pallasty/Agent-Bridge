# Engram G1.4 public-synthetic business component contract

Date: 2026-07-21  
Status: `DESIGN_CONTRACT_FROZEN__NO_IMPLEMENTATION_AUTHORITY`

## 1. Decision

The next component shape is a pure, public-synthetic world-state
transformation. It is intentionally smaller than a plugin system: one WIT
world, one export, no imports, bounded integer records, and a deterministic
report.

The frozen fixture package is:

- WIT: `scripts/eval/fixtures/engram_g14_business_component_contract_v0/world.wit`
- envelope and fixture contract:
  `scripts/eval/fixtures/engram_g14_business_component_contract_v0/contract.json`

Initial byte pins for this contract revision:

- WIT SHA-256: `67a4317d8b2664dcdd18223908dc003a03baef6513e13e37d8fa49d4868b9bd5`
- contract JSON SHA-256: `2c402a9ef2aa9fa3598815511cf5fda43f1bd7700d933415a9600fc02fdcfaf0`

This is a contract-design result only. It does not authorize building,
linking, executing, registering, deploying, or exposing the component.

## 2. Why a pure component first

The component must prove the semantic contract independently from host
capabilities. A pure function makes the first falsifiers crisp:

- input/output schema drift;
- arithmetic or overflow drift;
- component and contract hash mismatch;
- replay output mismatch; and
- accidental ambient capability imports.

It also prevents a successful synthetic report from being mistaken for proof
of filesystem, network, process, clock-isolation, sandbox, or production
authority.

## 3. WIT contract

The canonical WIT package is
`agent-bridge:g14-business-probe@0.1.0`, world `transform`, with one export:
`evaluate(world-state-input) -> world-state-report`.

`world-state-input` contains `revision`, `entity-count`, `occupied-cells`, and
`transition-count`. The output repeats those values and adds:

```
occupancy-per-mille = floor(occupied_cells * 1000 / max(entity_count, 1))
report-code = "WORLD_STATE_V0"
```

All arithmetic is checked. Values outside the bounded contract are invalid;
they are not clamped silently.

The component imports nothing. In particular, it does not import WASI clocks,
filesystem, network, subprocess, entropy, or poll. Host timestamps, if ever
needed for an outer evidence receipt, are host metadata and are not component
semantic inputs.

## 4. Invocation envelope

Any future host adapter must carry an outer canonical envelope with at least:

| Field | Rule |
| --- | --- |
| `schema` | exact contract schema identifier |
| `invocation_id` | globally unique for one attempt; never reused after failure |
| `contract_sha256` | exact bytes of `contract.json` |
| `component_sha256` | exact component bytes; no floating artifact path |
| `scope` | exactly `public-synthetic-v0`; no tenant/user/private value |
| `input` | WIT-compatible bounded record |
| `input_sha256` | hash of canonical input bytes |

The canonical serialization must reject duplicate keys, floats, non-standard
numbers, invalid UTF-8, unknown fields, and payloads beyond the limits. A
caller cannot omit hashes and receive a successful semantic result.

## 5. Output and replay receipt

The semantic output is accepted only when its canonical bytes match the WIT
result and the independently calculated fixture expectation. The outer result
must contain:

| Field | Rule |
| --- | --- |
| `status` | `ok` or a closed failure code |
| `output` | present only for `ok`, schema-valid and bounded |
| `output_sha256` | hash of canonical output bytes |
| `evidence` | independent host receipt, not component prose |
| `replay` | second invocation result and equality verdict |
| `verified` | true only after all independent checks pass |

Replay is a second one-shot invocation using the same immutable component and
input hashes. `verified=true` requires byte-identical output and matching
independent receipt fields. A component's own success flag is never sufficient.

## 6. Fail-closed matrix

| Falsifier | Required result |
| --- | --- |
| WIT/contract hash drift | `not_verified`, `contract_hash_mismatch` |
| component hash drift | `not_verified`, `component_hash_mismatch` |
| malformed, unknown, duplicate, or oversized input | `not_verified`, `input_invalid` |
| overflow or out-of-range value | `not_verified`, `input_out_of_bounds` |
| malformed or oversized output | `not_verified`, `output_invalid` |
| replay output differs | `not_verified`, `replay_mismatch` |
| unexpected import/capability | `not_verified`, `capability_import_violation` |
| timeout, host failure, or unavailable artifact | `not_verified`, `host_unavailable` |

None of these failures may be represented as a green empty acknowledgement.

## 7. Acceptance boundary

This contract may later open a separate public-synthetic implementation gate
only after an independent checker verifies:

1. exact WIT and envelope byte pins;
2. independent schema and arithmetic oracles;
3. happy-path and every fail-closed fixture;
4. replay equality and replay-mismatch evidence;
5. import-policy inspection; and
6. explicit false values for registry, MCP, production-write, private-data,
   and native-sandbox authority.

The contract itself does not authorize a Cargo dependency, WIT binding,
component build, runtime registration, release, deployment, or canary.
