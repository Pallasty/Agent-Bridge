# Free Recall Strategy R16 — C2A Build Result

Date: 2026-07-23

Status: **LOCAL BUILD PASS / INDEPENDENT LINUX PASS / C2A ACCEPTED / C2B-C2C CLOSED**

Source preregistration:
`docs/design/FREE_RECALL_STRATEGY_R15_C2A_SOURCE_PREREGISTRATION_2026_07_22.md`

## 1. Decision

C2A is accepted as a default-off, synthetic-only source boundary. The store
owns deterministic synthetic identity, immediate HMAC pseudonym derivation,
payload hashing, Slice B append, and the opaque attempt. The bridge owns only
a crate-private adapter to C1's coarse `Begin`/`Item`/`Close` errors.

The adapter has no startup wiring. Normal builds cannot construct it, and no
real key, configuration read, event producer, retrieval path, sync/export
path, MCP surface, release, or deployment is enabled.

## 2. Evidence

The directed source checker passed all 12 constraints:

- both features remain default-off and the bridge forwards only the synthetic
  store feature;
- no public projection or `StateStore` expansion exists;
- bridge imports neither SQLite nor raw observation events;
- no environment/CLI key path or startup injection exists;
- the provider is synthetic-only and derivation remains store-owned.

The store tests exercise only disposable databases:

1. open → two saved items → close forms a finalized trace;
2. an invalid item latches the attempt, writes no close, and cannot finalize;
3. duplicate item ordinal cannot form a finalized trace.

The bridge adapter unit test verifies each store error maps only to C1's
existing coarse error type. C1's existing controller tests continue to prove
that item failure latches and suppresses close, and that absent capability or
an empty batch emits nothing.

## 3. Local macOS gate

All commands used `--locked`:

```text
python3 scripts/eval/free_recall_strategy_r16_c2a_source.py
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

Results: checker `12/12`; store `3 passed`; bridge `5 passed`; both checks
passed. The remaining warnings are pre-existing mixed-script/dead-code and
unrelated private-interface warnings, not C2A failures.

## 4. Independent Linux replay — tb14

The exact changed C2A source files were compared by SHA-256 before replay.
tb14 used its private fixed toolchain:

- `rustc 1.94.0 (4a4ef493e 2026-03-02)`;
- `cargo 1.94.0 (85eff7c80 2026-01-15)`.

The same checker and four commands above were replayed with `--locked
--offline`. Results: checker `12/12`; store `3 passed`; bridge `5 passed`;
both feature checks passed.

## 5. Authority ledger and next gate

- C2A source/build: **accepted**;
- C2A runtime injection and real observation: **closed**;
- C2B trusted-key custody: **closed**;
- C2C runtime enablement, retrieval, sync/export, MCP/API, merge, release,
  and deployment: **closed**.

The next possible lane is C2B only: a separate owner-authorized design and
custody gate for a real provider, including key origin, redaction,
revocation, rotation, and observability rules. R16 grants none of it.
