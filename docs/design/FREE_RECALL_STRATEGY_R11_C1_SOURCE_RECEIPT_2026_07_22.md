# Free Recall Strategy R11 — C1 Source Receipt

Date: 2026-07-22

Status: **SOURCE LANDED / STATIC PASS / FEATURE BUILD UNVERIFIED / C2 CLOSED**

Parent gate:
`docs/design/FREE_RECALL_STRATEGY_R10_SESSION_CURATE_PRODUCER_RESULT_2026_07_22.md`

Static checker:
`scripts/eval/free_recall_strategy_r11_c1_source.py`

## 1. Authorized source

R11 implements only the C1 producer-orchestration source authorized after R10:

- a new default-off `ab-bridge` feature named
  `episode-observation-slice-c1`, with no forwarded store feature;
- one bridge-private curation-batch capability and attempt interface;
- one fail-open-core/fail-closed-sidecar run controller;
- an optional `Hub` capability field and builder method, both crate-private and
  absent by default;
- the frozen `session_curate` begin/save-success-item/complete-close call order;
- an explicit candidate outcome ledger separating auxiliary errors from
  duplicate and candidate-failure counts;
- source-level deterministic fake-capability and ledger tests.

There is no production capability implementation. `build_hub` does not inject
one, so a C1 feature-built binary would still have no path to a sink.

## 2. Candidate accounting correction

The previous code inferred duplicates with:

```text
candidates - saved - mixed_errors
```

where `mixed_errors` also included prior-handoff scan failures. That could
miscount duplicates and, with enough auxiliary failures, underflow.

R11 records saved, duplicate, lookup-error, and save-error outcomes explicitly.
Auxiliary errors remain in the outward error list, preserving presentation
order, but no longer influence `skipped_duplicates` or the lifecycle event's
candidate save-failure count.

## 3. C1 orchestration behavior

The run controller:

1. does nothing when the capability is absent or the candidate batch is empty;
2. calls `begin` only after auxiliary scanning and immediately before the
   candidate loop;
3. calls `observe_saved` only after `memory_save` succeeds;
4. assigns zero-based ordinals over successful saves only;
5. drops the attempt at the first item failure, suppressing later items and
   close while core curation continues;
6. closes only a positive, complete sequence;
7. treats begin/close failure as no episode/incomplete episode without changing
   the memory result.

The capability interface owns future identity, pseudonym derivation, hashing,
key access, and sink behavior. The C1 source supplies none of them.

## 4. Static evidence

- direct `rustfmt --check` passed for the new module and the three modified
  Rust implementation/test roots; `lib.rs` was excluded to avoid unrelated
  pre-existing module-order churn;
- `git diff --check` passed;
- the repository pre-commit hook was inspected and found to run
  `cargo check -p ab-bridge --all-targets` for Rust changes; the source-only
  commit therefore uses its documented `AGENT_BRIDGE_SKIP_PRECOMMIT=1` bypass,
  with staged-stat and static checks performed explicitly here;
- R11 checker canonical errors: `0`;
- directed source mutations rejected: `14 / 14`;
- two independent checker reports were byte-identical;
- report SHA-256:
  `b2727710073502301e2931ef3ea8faa67b9331ee6cf1fd908bf61836c7996bda`;
- checker SHA-256:
  `a4d7de96da9df23c92ba3cfe2d8dcb3a08aa5eb11cb1b97b145dabd32833a2f0`;
- orchestration module SHA-256:
  `b32d46475e7111267c0160301961a14601a0e27a98d408ed1fce5178814e562a`;
- `mcp_tools.rs` SHA-256:
  `da247b9f5abc494c13a29d716ba6aa1755b5b2686b4092e1927f6e674c023e8d`;
- `hub.rs` SHA-256:
  `3fa78e58f0a68a1a4ee960d89fe7c9152c34205ff5b4d9e3118a4ecc31fe0bd0`;
- tool-test source SHA-256:
  `fc2092ed3e268b26d12670bde781dee11c00fbc1a2de40fb2a22232c8281c9ef`.

The first checker selftest rejected `13 / 14` mutations because its synthetic
item-before-save mutation failed to move the token. The mutation generator was
corrected to swap the two anchors; canonical source had zero errors in that
run, and both subsequent full runs passed `14 / 14`. This is validator
correction evidence, not a hidden source failure.

## 5. Isolation evidence

The new module contains no `SqliteStore`, `StateStore`, `ab-store`, key-provider
implementation, environment/runtime loader, MCP/API surface, retrieval,
sync/export, or production observer implementation. The bridge feature is not
in `default`, does not activate Slice A/B, and does not alter `main.rs`.

No Cargo command ran. No Rust test ran. No database was opened. No sidecar event
was emitted. No real key, capture, runtime configuration, merge, release, or
deployment was touched.

## 6. Next gate

The next separately authorized gate is an isolated C1 feature build and test:

```text
cargo check -p ab-bridge --no-default-features \
  --features episode-observation-slice-c1 --locked
cargo test -p ab-bridge --no-default-features \
  --features episode-observation-slice-c1 \
  episode_observation_curation_batch --locked
```

That build gate must also execute the candidate-ledger test and independently
repeat the exact source on a clean Linux worktree. A pass would accept C1
orchestration only. It would not open C2 storage integration, trusted key
custody, runtime enablement, real producer execution, merge, release, or
deployment.
