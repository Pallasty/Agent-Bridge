# Free Recall Strategy R15 — C2A Source Preregistration

Date: 2026-07-22

Status: **PREREGISTERED / C2A SOURCE NOT YET IMPLEMENTED / C2B-C2C CLOSED**

Parent decision:
`docs/design/FREE_RECALL_STRATEGY_R14_C2A_INTERFACE_DECISION_2026_07_22.md`

## 1. Exact proposed source surface

R15 narrows C2A to four feature-gated files and no startup changes:

| Crate | Path | Purpose |
| --- | --- | --- |
| `ab-store` | `src/episode_observation_c2_synthetic.rs` | Store-owned opaque handle/attempt and deterministic synthetic provider. |
| `ab-store` | `src/lib.rs`, `src/sqlite/episode_observation_slice_b.rs` | Feature declarations/export and only the internal handoff to Slice B append. |
| `ab-bridge` | `src/episode_observation_curation_batch_c2_synthetic.rs` | Crate-private adapter implementing the C1 capability traits. |
| `ab-bridge` | `Cargo.toml`, `src/lib.rs` | Default-off feature/module declaration only. |

`main.rs`, `hub.rs`, `mcp_tools.rs`, `StateStore`, schema migration startup,
retrieval, sync/export, and public tool registries are explicitly excluded.

## 2. Feature contract

```text
ab-store/episode-observation-slice-c2-synthetic
  = episode-observation-slice-b

ab-bridge/episode-observation-slice-c2-synthetic
  = episode-observation-slice-c1
  + ab-store/episode-observation-slice-c2-synthetic
```

Both features are absent from defaults. The word `synthetic` is intentional:
there is no production C2 feature in R15 and no constructor reachable from
normal startup.

## 3. Store-owned contract

The store module may export one opaque `CurationBatchObservationHandle` and an
opaque attempt. Their only public operations are begin, observe a saved memory
key with a saved ordinal, and finish with item count. The handle owns:

- deterministic synthetic IDs and payload hashing;
- immediate HMAC pseudonym derivation using a fixed test-only key/epoch;
- internal conversion to Slice A event shapes;
- internal Slice B append invocation and error mapping.

It must not export a raw event, append operation, projection, SQLite handle,
key bytes, provider trait, or provider constructor. The bridge adapter may
map store failures to C1's existing coarse `Begin`/`Item`/`Close` errors only.

## 4. Test scope

R15 implementation must add only disposable-DB and in-process tests:

1. store handle: open → two saved items → close forms a finalized projection;
2. store handle: failed/duplicate item append cannot close a finalized trace;
3. absent/default construction path emits no event;
4. bridge adapter maps store attempt errors to C1's fail-closed controller;
5. source checker rejects default-on features, startup injection, StateStore
   mutation, bridge SQLite imports, public append/projection, environment/CLI
   key reads, and non-synthetic provider construction.

The C1 orchestration tests remain unchanged and must still pass.

## 5. Acceptance commands

```text
cargo check -p ab-store --no-default-features \
  --features episode-observation-slice-c2-synthetic --locked

cargo test -p ab-store --lib --no-default-features \
  --features episode-observation-slice-c2-synthetic \
  episode_observation_c2_synthetic --locked

cargo check -p ab-bridge --no-default-features \
  --features episode-observation-slice-c2-synthetic --locked

cargo test -p ab-bridge --lib --no-default-features \
  --features episode-observation-slice-c2-synthetic \
  episode_observation_curation_batch --locked
```

An independent Linux replay and a directed static checker are required before
C2A acceptance. Passing them does not authorize C2B key custody, C2C runtime
enablement, real capture, retrieval, merge, release, or deployment.

## 6. Negative authority

R15 does not authorize C2A source implementation yet. It authorizes no real
key, environment/config reading, startup injection, user database, live event,
retrieval, sync/export, MCP/API change, merge, release, deployment, training,
or BioCortex integration.
