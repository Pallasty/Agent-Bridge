# Free Recall Strategy R21 — C2B Live Keychain Validation Result

Date: 2026-07-23

Status: **ACCEPTED / ONE DISPOSABLE LIVE RUN COMPLETE / C2C CLOSED**

Preregistration:
`docs/design/FREE_RECALL_STRATEGY_R20_C2B_LIVE_KEYCHAIN_VALIDATION_PREREGISTRATION_2026_07_23.md`

## 1. Result

The authorized R20 source surface and one disposable macOS Keychain run
passed. The accepted C2B reader derived an episode item reference from the
real Keychain backend. Both temporary Generic Password items were removed
before the test returned success.

No existing item was read, updated, or deleted. No key bytes or backend error
details crossed the test boundary. No macOS access prompt appeared.

## 2. Source boundary

The implementation changed only:

- `crates/store/Cargo.toml`;
- `crates/store/src/lib.rs`;
- `crates/store/src/episode_observation_c2_keychain_macos_live_lab.rs`;
- `scripts/eval/free_recall_strategy_r21_c2b_live_lab_source.py`.

The accepted production reader remained unchanged. The new feature is
default-off and the live module is gated by `test`, the dedicated feature,
and `target_os = "macos"`.

The lab deliberately uses `SecKeychain::add_generic_password`, not
`set_generic_password`: duplicate accounts fail rather than updating an
existing item. Presence checks request attributes only and never request
password data.

## 3. Evidence

Static source gate:

```text
18/18 boundary checks PASS
18/18 directed mutation checks PASS
git diff --check PASS
```

Fake-reader and ignored-test gate:

```text
5 passed; 0 failed; 1 ignored
```

External preflight:

```text
R20_PREFLIGHT_ABSENT
```

Exactly one authorized live invocation:

```text
episode_observation_c2_keychain_macos_live_lab::tests::
disposable_keychain_round_trip_cleans_up ... ok

1 passed; 0 failed
```

The live test retained its random public epoch and exact key account in
process through both post-cleanup absence checks. The identifier was not
printed on the successful path; cleanup failures would have reported only
the public account identifier, never the key.

External fixed-pointer postcheck:

```text
R20_POSTCHECK_ACTIVE_ABSENT
```

The random key account was checked absent inside the same guarded test before
success. The fixed `active-epoch` account was additionally checked absent by
the metadata-only `/usr/bin/security find-generic-password` command after the
test.

## 4. Cleanup and authority conclusion

The explicit normal-path cleanup deleted `active-epoch` first and the random
key account second. The guard owned only writes that had succeeded and would
retry those exact deletions on unwind. A successful test required both
metadata-only post-cleanup absence checks.

This result accepts only the C2B real-backend custody source validation. It
does not authorize C2C, runtime construction, bridge/MCP integration, merge to
master, release, deployment, production keys, persistent Keychain entries, or
rotation operations.
