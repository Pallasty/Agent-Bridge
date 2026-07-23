# Free Recall Strategy R20 — C2B Live Keychain Validation Preregistration

Date: 2026-07-23

Status: **PREREGISTERED / LIVE KEYCHAIN MUTATION NOT AUTHORIZED / C2C CLOSED**

Parent source acceptance:
`docs/design/FREE_RECALL_STRATEGY_R19_C2B_SOURCE_RESULT_2026_07_23.md`

## 1. Goal

R20 defines one disposable macOS Keychain round trip that validates the
accepted C2B reader against the real OS backend. It does not validate runtime
integration, production custody, rotation operations, or C2C.

No existing or user-supplied key may be used. The lab creates one random
32-byte key in process memory, writes two disposable Generic Password items,
derives one item reference through the accepted reader, and removes both
items before reporting success.

## 2. Why a dedicated lab is required

`/usr/bin/security help add-generic-password` states that passing a password
to `-w` is insecure. Interactive `-w` would avoid process arguments but would
require manual secret entry and expose the test to terminal capture mistakes.

R20 therefore uses a Rust test-only harness. It generates the key with
`ring::rand::SystemRandom`, never prints it, never accepts it through an
argument, environment variable, file, database, or prompt, and zeroizes its
local buffer after the Keychain write.

## 3. Exact source surface

| Path | Purpose |
| --- | --- |
| `crates/store/Cargo.toml` | Add a default-off `episode-observation-c2-keychain-macos-live-lab` feature depending only on the accepted C2B feature. |
| `crates/store/src/lib.rs` | Declare one module only under `cfg(all(test, feature, target_os = "macos"))`. |
| `crates/store/src/episode_observation_c2_keychain_macos_live_lab.rs` | One ignored real-Keychain round-trip test and cleanup guard. |
| `scripts/eval/free_recall_strategy_r21_c2b_live_lab_source.py` | Reject authority expansion and require cleanup/preflight structure. |

The accepted production reader file is not changed. No bridge, hub, main,
MCP, SQLite, retrieval, sync/export, or deployment file is in scope.

## 4. Disposable namespace and order

The service remains the accepted fixed namespace:

```text
com.agent-bridge.episode-ref.v1
```

Accounts:

```text
active-epoch
key:c2b-live-<16 lowercase hex characters>
```

The lab performs this exact state sequence:

1. confirm `active-epoch` does not exist; otherwise abort without mutation;
2. generate a random epoch suffix and confirm its key account does not exist;
3. generate 32 random key bytes in memory;
4. write the key account first;
5. write `active-epoch` last;
6. zeroize the local key buffer;
7. call the accepted crate-private Keychain derivation once;
8. verify only the expected epoch prefix and output shape;
9. delete `active-epoch` first and the key account second;
10. verify both accounts are absent.

Writing the pointer last prevents a crash from exposing a pointer to a missing
key. Deleting the pointer first prevents cleanup from leaving a readable
active key.

## 5. Cleanup and interruption contract

A guard owns the two public account identifiers and tracks which writes
succeeded. Its `Drop` implementation attempts deletion in the required order.
The normal path also performs explicit deletion and post-cleanup absence
checks.

If a test is killed so abruptly that `Drop` cannot run, the result is
**INCOMPLETE / CLEANUP REQUIRED**, never PASS. The recovery command may delete
only the exact service plus the recorded random key account. The epoch and
account identifiers may be logged; key bytes and Keychain backend error text
may not.

The live run must retain its random epoch identifier in the test receipt until
post-cleanup absence is verified. No broader Keychain enumeration or deletion
is allowed.

## 6. Prompt and ownership policy

The Codex session owns creation, verification, and cleanup. macOS may present
an access-control prompt for the test binary. The run pauses for the owner to
approve only that prompt; cancellation is a valid fail-closed result.

The lab must not use `-A`, alter the login-keychain search list, unlock a
keychain, change ACLs, or request access to any existing entry.

## 7. Static and run gates

Source gate:

```text
python3 scripts/eval/free_recall_strategy_r21_c2b_live_lab_source.py
cargo test -p ab-store --lib --no-default-features \
  --features episode-observation-c2-keychain-macos-live-lab \
  episode_observation_c2_keychain_macos --locked --offline
```

The first test command runs only fake-reader tests; the real test is
`#[ignore]`.

Live run, separately authorized:

```text
cargo test -p ab-store --lib --no-default-features \
  --features episode-observation-c2-keychain-macos-live-lab \
  episode_observation_c2_keychain_macos_live_lab::tests::disposable_keychain_round_trip_cleans_up \
  --locked --offline -- --ignored --exact
```

Acceptance requires:

- preflight absence;
- one successful real derivation;
- no secret in arguments, environment, stdout/stderr, or repository;
- explicit cleanup success;
- post-cleanup absence for both exact accounts.

## 8. Negative authority

R20 does not authorize the source changes or live run yet. It authorizes no
existing Keychain access, user/production key, persistent entry, runtime
constructor, C2C, merge to master, release, or deployment.

The next valid action requires explicit owner authorization for both:

1. the exact test-only source surface in §3; and
2. one disposable live run under §§4–7, including acceptance of a possible
   macOS prompt and mandatory cleanup.
