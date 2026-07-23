# Free Recall Strategy R24 — C2C-B Startup Wiring Preregistration

Date: 2026-07-23

Status: **AMENDED DESIGN DECISION / R25 SOURCE NOT AUTHORIZED / LIVE C2C CLOSED**

Parents: R22 C2C runtime design and R23 source commit `929ea5cc`. R23 passed local gates; its independent Linux replay was explicitly waived by the owner and is not represented as independent acceptance.

## 1. Goal

R24 defines the next separately authorized C2C-B source packet: an explicit macOS startup path that may assemble the accepted C1 seam with a store-owned Keychain provider. It authorizes no source, Keychain access, user database, live observation, merge, release, or deployment.

The observer may exist only when all five operands hold:

```text
macOS target AND C2C-B feature compiled AND exact daemon/MCP CLI value
AND fixed Keychain custody preflight succeeded AND store assembly succeeded
```

Any missing operand leaves the Hub observer absent and core curation unchanged.

## 2. Operator surface

The only proposed spellings are:

```text
agent-bridge daemon --episode-observation keychain-macos-v1
agent-bridge mcp    --episode-observation keychain-macos-v1
```

Omission keeps current behavior. The implicit no-subcommand daemon route cannot enable observation. Other subcommands reject this option. The option is authorization only: it must not name a service, account, epoch, key, path, URL, environment variable, JSON value, or MCP argument. The compiled macOS feature fixes the backend.

## 3. Custody readiness

The store constructor may read only `com.agent-bridge.episode-ref.v1`, `active-epoch`, and `key:<active epoch>`. Before C1 injection it performs one bounded readiness derivation with an internal non-user memory key, discards the resulting reference, and relies on the accepted C2B reader to zeroize returned bytes. Unavailable, revoked, malformed, or wrong-length custody therefore produces zero episode events.

Only coarse `Unavailable` may cross to bridge. Epochs, accounts, backend messages, and key bytes remain inside `ab-store`; no log, CLI, MCP output, or Hub field may contain them.

## 4. Exact proposed R25 source surface

| Crate | Path | Purpose |
| --- | --- | --- |
| `ab-store` | `Cargo.toml` | Default-off `episode-observation-c2c-keychain-macos-runtime`. |
| `ab-store` | `src/lib.rs` | macOS/feature-gated private runtime declaration. |
| `ab-store` | `src/episode_observation_c2_keychain_macos_runtime.rs` | Opaque handle/attempt, readiness preflight, immediate derivation. |
| `ab-store` | `src/sqlite/episode_observation_slice_b.rs` | Private feature-gated explicit-runtime append gate; no schema change. |
| `ab-bridge` | `Cargo.toml` | Default-off forwarding feature plus C1. |
| `ab-bridge` | `src/lib.rs` | Feature-gated private adapter declaration. |
| `ab-bridge` | `src/episode_observation_curation_batch_c2_keychain_macos.rs` | Crate-private adapter mapping coarse Begin/Item/Close only. |
| `ab-bridge` | `src/main.rs` | Parse exact daemon/MCP value and attempt all-or-nothing HubBuilder injection. |
| root | `scripts/eval/free_recall_strategy_r25_c2c_b_startup_source.py` | Static scope and authority checker. |

`hub.rs`, `mcp_tools.rs`, `StateStore`, schemas/migrations, setup, hooks, sync/export, retrieval, public registries, deployment scripts, and C2B reader source remain unchanged.

## 5. Feature and startup contract

```text
ab-store/episode-observation-c2c-keychain-macos-runtime
  = episode-observation-slice-b + episode-observation-c2-keychain-macos

ab-bridge/episode-observation-c2c-keychain-macos-runtime
  = episode-observation-slice-c1 + ab-store/episode-observation-c2c-keychain-macos-runtime
```

Both features are absent from defaults and all real Keychain modules are additionally macOS-gated. Linux feature builds must have no real provider constructor. `build_hub` receives a typed private authorization parsed only from the two allowed command variants. A failed readiness or constructor attempt supplies `None` to the existing HubBuilder; the daemon/MCP remains available and may emit only the redacted local debug message `episode observation unavailable`.

No provider is global or bridge-owned. A successful store handle owns only the store and derives references immediately; it never returns key material, provider traits, raw events, SQLite handles, epochs, or Keychain errors across the crate boundary.

## 6. Required R25 gates

R25 must prove: default and bare commands construct no observer; unsupported spellings fail parse; fake-unavailable custody injects nothing; a macOS fake reader proves readiness before open; explicit disposable-DB assembly yields one bounded open → item → close trace without Keychain; begin/item/close/append/readiness failures yield no finalized trace and do not alter core curation; bridge has no custody vocabulary/import; no source writes, unlocks, alters ACLs, or enumerates Keychain.

```text
python3 scripts/eval/free_recall_strategy_r25_c2c_b_startup_source.py
cargo check -p ab-store --no-default-features --features episode-observation-c2c-keychain-macos-runtime --locked
cargo check -p ab-bridge --no-default-features --features episode-observation-c2c-keychain-macos-runtime --locked
cargo test -p ab-store --lib --no-default-features --features episode-observation-c2c-keychain-macos-runtime episode_observation_c2_keychain_macos_runtime --locked --offline
cargo test -p ab-bridge --lib --no-default-features --features episode-observation-c2c-keychain-macos-runtime episode_observation_curation_batch_c2_keychain_macos --locked --offline
```

An independent macOS replay is required for R25 source acceptance. Linux may only replay default-off absence.

## 7. R26 remains separate

After R25, a live C2C run still needs new owner authorization naming an exact disposable database, the exact disposable/pre-existing Keychain entries, one bounded `session_curate` fixture, post-run event evidence, Keychain cleanup proof, and rollback handling.

## 8. Negative authority

R24 authorizes this document only. It grants no R25 edits, Keychain read/write, CLI addition, normal-process provider construction, user database access, live observation, merge, release, deployment, retrieval, sync/export, MCP/API exposure, training, or BioCortex integration. The next valid action is explicit owner authorization for exactly the R25 surface and gates above; R26 remains closed.

## Amendment A — binary/library visibility correction

Review of the actual Rust crate boundary found that `main.rs` is a separate binary crate. It cannot call the existing crate-private `HubBuilder::curation_batch_observer`, and a public HubBuilder method taking the crate-private capability trait would be unusable. The original private bridge adapter therefore could not perform the proposed startup wiring.

R25 replaces that adapter row with `ab-bridge/src/episode_observation_c2c_keychain_macos_runtime.rs`, a feature-gated public attachment function with this narrow shape:

```text
attach_explicit_keychain_macos_observer(HubBuilder, Arc<SqliteStore>) -> HubBuilder
```

It is the only public binary-to-library bridge. It receives no key, account, epoch, provider trait, event, or Keychain error. It constructs the store-owned opaque handle, maps failure to no injection, and invokes the existing crate-private HubBuilder seam inside the library crate. `hub.rs` remains unchanged.

The store runtime module exports only its opaque handle/factory under the default-off macOS feature; it exports no provider interface or raw custody material. This correction changes no live authority, test gate, or R26 boundary.
