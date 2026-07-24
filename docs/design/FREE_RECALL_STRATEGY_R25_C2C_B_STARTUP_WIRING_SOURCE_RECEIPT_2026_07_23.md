# Free Recall Strategy R25 — C2C-B Startup Wiring Source Receipt

Date: 2026-07-23

Status: **LOCAL SOURCE PASS / INDEPENDENT macOS REPLAY PENDING / LIVE C2C CLOSED**

Parents: R24 C2C-B startup-wiring preregistration and source commit
`d2b7527c`.

## 1. Scope exercised

R25 adds the pre-registered, default-off macOS runtime assembly surface only:

- `ab-store` owns the opaque Keychain-backed readiness handle and immediate
  reference derivation;
- `ab-bridge` owns a narrow binary-to-library attachment function, which maps
  unavailable custody to no Hub observer;
- only `daemon` and `mcp` accept the typed
  `--episode-observation keychain-macos-v1` spelling;
- the attachment site additionally requires the macOS target and the
  `episode-observation-c2c-keychain-macos-runtime` feature.

No migration, schema, Hub seam, MCP tool, sync/export/retrieval surface,
deployment script, or C2B reader was changed.

## 2. Default-off and custody boundary

The feature is absent from both crate defaults. Without the feature, no real
runtime module is compiled. With the feature, omission of the CLI option and
the implicit daemon route retain a `None` authorization; no observer is
attached. An unavailable or malformed readiness derivation returns only the
coarse `Unavailable` result to the bridge, which leaves the builder unchanged.

The bridge receives neither key bytes, epoch, account, provider trait, raw
Keychain error, SQLite handle, nor item reference. It performs no custody
operation. The store reader is unchanged and the new runtime source contains
no Keychain write, delete, unlock, ACL alteration, enumeration, environment
selection, or logging path.

## 3. Local evidence

The following completed on the macOS implementation host without running the
real `keychain-macos-v1` path:

```text
python3 scripts/eval/free_recall_strategy_r25_c2c_b_startup_source.py
  -> 18 static contract checks PASS; 16 directed mutation checks PASS

cargo test -p ab-store --lib --no-default-features \
  --features episode-observation-c2c-keychain-macos-runtime \
  episode_observation_c2_keychain_macos_runtime --locked --offline
  -> PASS (fake readiness failure and fake bounded open -> item -> close)

cargo test -p ab-bridge --lib --no-default-features \
  --features episode-observation-c2c-keychain-macos-runtime \
  episode_observation_c2c_keychain_macos_runtime --locked --offline
  -> PASS (unavailable store handle injects no observer)

cargo check -p ab-store --no-default-features \
  --features episode-observation-c2c-keychain-macos-runtime --locked
  -> PASS

cargo check -p ab-bridge --no-default-features \
  --features episode-observation-c2c-keychain-macos-runtime --locked
  -> PASS
```

The parser contract is additionally source-gated: the typed mode is present
only on `Daemon`/`Mcp`, the implicit daemon path is `None`, and no environment
variable can enable it. A later CLI process-level replay must run only after
the current shared release build no longer holds the Cargo lock; it must still
avoid the explicit Keychain option unless R26 is separately authorized.

## 4. What remains unproven

R24 requires an **independent macOS replay** for R25 source acceptance. The
available second macOS tailnet peer was online but rejected the configured
public-key authentication before any remote command ran. This receipt therefore
does not claim independent acceptance.

Linux can establish only default-off absence. It cannot substitute for this
gate. The local tests above establish source structure and fake-custody
behavior, not a real provider invocation.

## 5. Next bounded actions

1. Restore a single authenticated, non-interactive SSH path to an independent
   macOS node and replay the source/check commands from §3 there. Do not use
   the explicit runtime CLI option during that replay.
2. Record that independent evidence in a result document and only then mark
   R25 source accepted.
3. Keep R26 closed. A real C2C run needs a new, itemized authorization naming
   a disposable database, the exact disposable Keychain entries, one bounded
   `session_curate` fixture, cleanup proof, and rollback handling.
