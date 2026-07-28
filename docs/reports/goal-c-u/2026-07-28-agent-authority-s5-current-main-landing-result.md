# Agent authority S5 current-main landing result

Date: 2026-07-28

Status: **VERIFIED_ISOLATED_LANDING_BRANCH**

Runtime authority: **NONE**

## Result

The complete S0-S5 authority evidence lineage is executable on the current
master composition without weakening S1's historical source pin or presenting
historical coverage as a current-runtime claim.

The landing branch remains isolated:

```text
codex/agent-authority-s5-current-main-landing-20260728
```

Its verified implementation commits are:

```text
c8a6543071684af56f2b89d62aff0be8659f501f
  fix(agent-authority): preserve S1 historical source replay

2a21577cce4ac7b9f70caeba9ce39929f245160c
  test(lswr): reconcile readonly snapshot fixtures
```

The branch descends from the immutable S5 result
`dc90f19fc83df7181708c4e05c2af35dd0b6e4ec`. Current master
`0b95c231b4ac61743c297b45b0abf81690bd3fd6` is also an ancestor through
the S5 composition.

## S1 historical replay

The historical S1 pin remains unchanged:

```text
source commit:
  a1c9469e9a14cd73159d34974f0e99714ce5a1f0
historical source SHA-256:
  d8b89e32212f2df1a5188c5d47addcc912f2f0b17518861cb53dea08d7cc1707
historical source bytes:
  1205712
```

The deterministic gzip snapshot is:

```text
path:
  crates/bridge/tests/fixtures/
  agent_compromise_resilience_s1_t6_tests_a1c9469.rs.gz
bytes:
  175455
SHA-256:
  7377fc1297da8253847e6a225e8e7b2e59c048468184f8757747a024d3da4b98
```

Regenerating it with `git show ... | gzip -n -9` produced byte-identical
output. The loader verifies the compressed hash, bounds decompression to one
byte beyond the expected length, requires the exact uncompressed length, and
verifies the unchanged historical hash before returning borrowed bytes.

The live current `mcp_tools/tests.rs` remains separate. Its observed hash is
`118115073ef051c478eb109694d8ef0a8993af1f0f89dafde5131011b8b30289`,
and validation against the historical pin returns the exact fail-closed
diagnostic:

```text
t6_tests source hash changed
```

## TDD evidence

Before the loader existed, the focused test failed to compile with only the
intended missing `load_frozen_t6_test_snapshot` symbol (`E0425`). It did not
fail because of dependency download, malformed JSON, missing current source,
or an unrelated crate.

After implementation:

- S1: 5 passed, 0 failed;
- historical report runs were byte-identical;
- report SHA-256:
  `b3927bd4869c337f2dcad57ba8b9a8369f25e0de12d0edd1f40f97b877ebb115`;
- categories: 10;
- covered / partial / gap: 0 / 5 / 5;
- every authority field: false.

`flate2` is a direct development dependency only. It was already present in
the frozen lock file as a transitive package; the only lock change adds it to
`ab-bridge`'s package dependency list. The depth-one normal dependency graph
has no direct `flate2` edge.

## Current-master fixture blocker

The first broad test exposed a separate existing current-master failure:

```text
lswr_readonly_bridge_consumer::
consumer_summary_fixture_matches_generated_detailed_summary
```

The untouched S5 result reproduced the same failure, and all relevant Git
blobs are identical between current master and S5. Both the independent
hardcoded snapshot and ledger-file round-trip derive:

```text
sha256:9ab9297aa85d3ac5e0db9e21d98f20e134a94991819d48ca1a1880a6d421137e
```

Seven derived LSWR fixtures retained the older digest
`5ff171f505327b9d93f01a1dfc44a6159a00f48e6085a5e7a63e5eded6629495`.
Five JSON artifacts and the detailed report were regenerated with existing
typed examples. Normalizing only the old digest made every old/new artifact
equal. The counts-only report was then validated by its existing renderer
test.

No LSWR source behavior changed. The focused fixture chain passed 30 tests
with zero failures, and the stale digest has zero remaining occurrences in
that lane.

## Verification matrix

- S0: 4 passed, 0 failed.
- S1: 5 passed, 0 failed.
- S2: 6 passed, 0 failed.
- S3: 7 passed, 0 failed.
- S4: 8 passed, 0 failed.
- S5: 8 passed, 0 failed, 2 ignored helpers.
- inherited S7: 12 passed, 0 failed, 3 ignored helpers.
- focused LSWR derived fixture chain: 30 passed, 0 failed.
- `ab-store` feature off: check passed.
- `ab-store` S5 feature on: check passed.
- `ab-bridge --all-targets --no-default-features`: check passed.
- `ab-bridge --all-targets --no-default-features`: test passed; main library
  reported 1687 passed, 0 failed, 4 ignored, and every subsequent target
  reported zero failures.
- repository pre-commit default-feature `ab-bridge --all-targets`: passed on
  the exact staged S1 implementation.
- JSON parsing, deterministic gzip regeneration, report determinism,
  `rustfmt --check`, `git diff --check`, credential/private-key scan,
  ancestry checks, and changed-runtime-source scan: passed.

One intermediate broad rerun supplied `--quiet` twice and exited before
executing tests. Removing the duplicate harness option produced the successful
full run above.

Existing repository warnings remain for mixed-script test naming, unused
code, and the `ToolPolicy` visibility boundary. No warning was introduced by
the S1 loader after its live-source constant was restricted to test builds.

## Nonclaims

This result does not claim that current T6 guards still provide the historical
S1 coverage, that current runtime containment is safe, or that the whole
repository lacks additional guards.

No production/private key, signing operation, live `state.db`, runtime
receiver, MCP/CLI/daemon/StateStore caller, memory/graph/session/retrieval
mutation, runtime/shadow/executor enablement, deployment, master update, or
production authority was introduced or exercised.
