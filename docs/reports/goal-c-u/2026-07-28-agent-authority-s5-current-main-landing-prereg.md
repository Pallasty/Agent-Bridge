# Agent authority S5 current-main landing preregistration

Date: 2026-07-28

Status: **FROZEN_BEFORE_IMPLEMENTATION**

## Research question

Can the complete S0-S5 authority evidence lineage remain executable on current
master without weakening S1's historical source pin or misrepresenting old
coverage as a current-runtime claim?

## Hypothesis

A test-only deterministic snapshot loader can replay the exact S1-reviewed
`mcp_tools/tests.rs` bytes while a separate live-source check continues to
reject drift. This should turn the known master-landing red test into two
explicit, simultaneously testable facts:

- historical S1 replay passes against its exact reviewed source;
- current live source differs and is rejected by the unchanged frozen pin.

## Frozen identities

| Item | Identity |
|---|---|
| current master | `0b95c231b4ac61743c297b45b0abf81690bd3fd6` |
| S5 result | `dc90f19fc83df7181708c4e05c2af35dd0b6e4ec` |
| S1 T6 source commit | `a1c9469e9a14cd73159d34974f0e99714ce5a1f0` |
| S1 historical source blob | `899614fba02e31bb96566e53e6709853d430e706` |
| S1 historical source SHA-256 | `d8b89e32212f2df1a5188c5d47addcc912f2f0b17518861cb53dea08d7cc1707` |
| S1 historical source bytes | `1205712` |
| deterministic gzip SHA-256 | `7377fc1297da8253847e6a225e8e7b2e59c048468184f8757747a024d3da4b98` |
| deterministic gzip bytes | `175455` |
| observed current source SHA-256 | `118115073ef051c478eb109694d8ef0a8993af1f0f89dafde5131011b8b30289` |

## Frozen failure

The current S5 result tree was tested before this preregistration:

```text
running 4 tests
2 passed
2 failed

mapping evaluates: t6_tests source hash changed
first evaluation: t6_tests source hash changed
```

This is the landing blocker. Changing the mapping fixture's historical hash to
the current hash is forbidden.

## Planned implementation

1. Add the deterministic gzip artifact under bridge test fixtures.
2. Add `flate2` only as an `ab-bridge` development dependency.
3. Add a bounded in-process historical snapshot loader with compressed hash,
   uncompressed length, and uncompressed hash checks.
4. Give embedded source views ordinary borrowed lifetimes so decompressed bytes
   need not be leaked.
5. Make the historical S1 executable/tests consume the verified snapshot.
6. Add one test that compares live validation outcome with exact frozen-hash
   equality and requires the existing source-hash error on drift.
7. Do not alter the S1 mapping JSON, expected category statuses, source path,
   historical result documents, or authority fields.

## Falsifiers

The hypothesis is false if:

- the artifact does not reconstruct the exact frozen Git blob;
- any historical source pin or expected mapping status changes;
- a drifted live source validates against the historical mapping;
- the historical report becomes nondeterministic;
- a full all-target test still contains a deterministic S0-S5 failure;
- a normal runtime build acquires a snapshot loader or new capability; or
- any authority field becomes true.

## Boundary

This landing gate may create a worktree, test-only artifact, tests,
documentation, commits, and isolated dual-remote branch. It may not update
master, deploy, enable runtime/shadow/executor behavior, open live state,
change credentials or permissions, rewrite history, or grant authority.
