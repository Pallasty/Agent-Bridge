# Agent authority S5 current-main landing with frozen S1 source replay

Date: 2026-07-28

Status: **PREREGISTERED_TEST_ONLY_LANDING_HARDENING**

Runtime authority: **NONE**

## Decision

The S0-S5 authority lineage cannot be merged directly into current master
while its S1 example has two deterministic failing tests. The failures are
correct for a live-source audit:

```text
t6_tests source hash changed
```

They are not acceptable as a permanent master test state.

The historical S1 source pin must remain:

```text
d8b89e32212f2df1a5188c5d47addcc912f2f0b17518861cb53dea08d7cc1707
```

S1 landing hardening will therefore separate two questions:

1. Can the frozen S1 mapping still be replayed exactly against the source bytes
   it reviewed?
2. Does the live current source still match those historical bytes?

The first uses a byte-exact historical snapshot. The second remains a
fail-closed live-source drift check. Neither result becomes runtime authority.

## Verified starting point

- local, GitLab, and GitHub master:
  `0b95c231b4ac61743c297b45b0abf81690bd3fd6`;
- S5 result on both remotes:
  `dc90f19fc83df7181708c4e05c2af35dd0b6e4ec`;
- current-master/S5 merge-tree preview:
  conflict-free tree `2900e563d99126cb5cf7687eacff5d24e97f96ae`;
- branch delta:
  39 files, 17,432 insertions, 1 deletion;
- fresh S1 current-tree test:
  2 passed, 2 failed;
- frozen S1 test at the S4 result:
  4 passed, 0 failed.

The two current-tree failures are only:

```text
frozen_mapping_derives_five_partial_and_five_gaps
report_is_deterministic_and_non_authorizing
```

Both stop at the exact frozen source-hash check.

## Snapshot identity

The source declared by the original S1 mapping is:

```text
commit: a1c9469e9a14cd73159d34974f0e99714ce5a1f0
path:   crates/bridge/src/mcp_tools/tests.rs
blob:   899614fba02e31bb96566e53e6709853d430e706
bytes:  1205712
sha256: d8b89e32212f2df1a5188c5d47addcc912f2f0b17518861cb53dea08d7cc1707
```

The same blob is present at the frozen S4 result
`17d106f21d4540b81c609eaaf8fca7ce9462faf6`.

To avoid adding a second 1.2 MiB Rust source file, the landing branch stores a
deterministic gzip artifact:

```text
path:
  crates/bridge/tests/fixtures/
  agent_compromise_resilience_s1_t6_tests_a1c9469.rs.gz

generation:
  git show a1c9469e9a14cd73159d34974f0e99714ce5a1f0:
  crates/bridge/src/mcp_tools/tests.rs | gzip -n -9

compressed bytes: 175455
compressed sha256:
  7377fc1297da8253847e6a225e8e7b2e59c048468184f8757747a024d3da4b98
```

The loader must verify the compressed SHA-256, decompress without invoking an
external process, require the exact uncompressed length, and require the
original S1 SHA-256 before returning bytes.

## Executable contract

The S1 example becomes an explicitly historical replay:

1. load the unchanged S1 mapping and S0 corpus;
2. load and verify the deterministic historical `tests.rs` snapshot;
3. continue using the unchanged live `memory_biocortex.rs`, whose SHA-256
   still matches the frozen pin;
4. validate every historical source pin and anchor against those exact bytes;
5. derive the original five partial and five gap statuses;
6. preserve the original all-false authority report; and
7. separately evaluate live `mcp_tools/tests.rs` against the frozen pin.

The live-source invariant is:

```text
live hash == frozen hash  -> frozen validation may pass
live hash != frozen hash  -> exact fail-closed source-hash error is required
```

The current live hash is observed as:

```text
118115073ef051c478eb109694d8ef0a8993af1f0f89dafde5131011b8b30289
```

That value is landing evidence, not a replacement source pin.

## TDD contract

Before implementation, a focused test referencing the missing historical
snapshot loader must fail to compile. The RED is invalid if it comes from
dependency download, malformed JSON, a missing current source file, or an
unrelated crate.

Expected GREEN tests:

1. frozen mapping derives five partial and five gaps from the historical
   snapshot;
2. stale historical pins and missing anchors fail closed;
3. malformed partitions and expected statuses fail closed;
4. the historical report is deterministic and non-authorizing; and
5. live-source validation is equivalent to exact hash equality and returns the
   source-hash diagnostic on drift.

## Verification ladder

- deterministic artifact generation and compressed/uncompressed hashes;
- missing-loader RED;
- focused S1 tests;
- two byte-identical S1 historical report runs;
- S0, S2, S3, S4, S5, and inherited S7 focused regressions;
- `ab-store` feature-off and S5 feature-on checks;
- `ab-bridge --all-targets --no-default-features` check;
- broad `ab-bridge --all-targets --no-default-features` test;
- JSON parsing, formatting, staged diff, credential/private-key scan, and
  runtime/public-surface scan;
- implementation/result commits and dual-remote landing-branch verification.

## Nonclaims

The snapshot does not prove that current T6 guards still provide the historical
coverage, that the whole repository lacks a guard, or that current runtime
containment is safe. It preserves a historical review and exposes current
drift as a separate observation.

No production/private key, signing operation, live `state.db`, runtime receiver,
MCP/CLI/daemon/StateStore caller, memory/graph/session/retrieval mutation,
runtime/shadow/executor enablement, deployment, master update, or production
authority is admitted.
