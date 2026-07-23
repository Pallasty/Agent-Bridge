# Free Recall Strategy R18 — C2B macOS Keychain Source Preregistration

Date: 2026-07-23

Status: **PREREGISTERED / C2B SOURCE NOT AUTHORIZED / C2C CLOSED**

Parent decision:
`docs/design/FREE_RECALL_STRATEGY_R17_C2B_KEY_CUSTODY_DESIGN_2026_07_23.md`

## 1. Backend decision

The first C2B backend is macOS Keychain Generic Password, read-only, using
the already locked crates:

- `security-framework = 3.7.0`;
- `zeroize = 1.8.2`.

No installation, account access, key generation, import, rotation, deletion,
or runtime construction is authorized by R18.

The fixed Keychain namespace is:

```text
service: com.agent-bridge.episode-ref.v1
account: active-epoch       data: validated UTF-8 epoch identifier
account: key:<epoch>        data: exactly 32 secret bytes
```

The service and account format are public identifiers, not configuration.
They are constants in store code and cannot be overridden by environment,
CLI, MCP, SQLite, or a repository file.

## 2. Exact source surface

| Crate | Path | Authorized purpose |
| --- | --- | --- |
| `ab-store` | `Cargo.toml` | Add one default-off macOS-only feature and optional locked dependencies. |
| `ab-store` | `src/lib.rs` | Declare one private, target-gated module. |
| `ab-store` | `src/episode_observation_c2_keychain_macos.rs` | Read-only Keychain reader, bounded secret wrapper, validation, and fake-reader tests. |
| workspace | `Cargo.lock` | Record only the new direct optional dependency edges; package versions and checksums remain unchanged. |
| repository | `scripts/eval/free_recall_strategy_r19_c2b_source.py` | Directed static boundary checker. |

No `ab-bridge` file is in scope. `main.rs`, `hub.rs`, `mcp_tools.rs`,
`StateStore`, schema/migrations, runtime configuration, retrieval, sync/export,
and public registries are excluded.

## 3. Feature contract

```text
ab-store/episode-observation-c2-keychain-macos
  = episode-observation-slice-b
  + dep:security-framework
  + dep:zeroize
```

The feature is absent from defaults. The module is additionally guarded by
`target_os = "macos"`. Enabling the feature on Linux may compile the package
for portability checking, but creates no provider or fallback backend.

## 4. Internal contract

The module may contain only:

- a private `KeychainSecretReader` trait used to replace OS I/O in tests;
- a private macOS implementation that performs Generic Password reads only;
- a private bounded secret buffer that zeroizes on drop;
- a private validated `(epoch, key)` acquisition result;
- a crate-private constructor reserved for a future C2C packet.

Acquisition order is fixed:

1. read `active-epoch`;
2. validate the epoch with Slice A's existing grammar;
3. read `key:<epoch>`;
4. require exactly 32 bytes;
5. lend the bytes to one item-reference derivation;
6. zeroize the owned buffer before returning.

The key, Keychain response, or owned buffer must never implement `Clone`,
`Debug`, `Display`, serialization, or conversion to a public type. Errors are
closed enums with no backend message or secret-bearing payload.

## 5. Forbidden source

The C2B source gate must reject:

- Keychain write, update, delete, import, generation, or enumeration APIs;
- environment/CLI/MCP/SQLite selection of service, account, epoch, or key;
- logging, formatting, panic interpolation, serialization, or persistence of
  key bytes or Keychain error text;
- a public provider, public constructor, bridge import, startup injection, or
  global cache;
- fallback to the C2A synthetic key when Keychain access fails;
- accepting a key shorter or longer than 32 bytes;
- retaining the owned Keychain buffer in an observation attempt.

## 6. Required tests

All automated tests use a deterministic in-memory fake reader. They must prove:

1. valid active epoch plus a 32-byte key performs one derivation and zeroizes
   the temporary buffer;
2. missing active epoch, invalid UTF-8, invalid epoch grammar, missing key,
   short key, and long key each fail closed;
3. an epoch change causes the next acquisition to read the new account without
   rewriting old references;
4. backend error text and sentinel secret bytes do not appear in returned
   errors or captured tracing output;
5. normal/default construction performs zero reads;
6. source-checker mutations reject every forbidden path in §5.

No test may access the user's login Keychain or request a Keychain prompt.

## 7. Acceptance commands

macOS source gate:

```text
python3 scripts/eval/free_recall_strategy_r19_c2b_source.py
cargo check -p ab-store --no-default-features \
  --features episode-observation-c2-keychain-macos --locked --offline
cargo test -p ab-store --lib --no-default-features \
  --features episode-observation-c2-keychain-macos \
  episode_observation_c2_keychain_macos --locked --offline
```

Independent Linux portability replay:

```text
python3 scripts/eval/free_recall_strategy_r19_c2b_source.py
cargo check -p ab-store --no-default-features \
  --features episode-observation-c2-keychain-macos --locked --offline
```

Linux does not validate Keychain behavior; it validates feature isolation,
target gating, and absence of an ambient fallback. C2B acceptance additionally
requires an independent review of the macOS test output and source hashes.

## 8. Negative authority

R18 authorizes no C2B source implementation. It grants no access to a real
Keychain, no dependency or lockfile change, no runtime constructor, no C2C,
no real observation, no merge to master, release, or deployment.

The next valid action is explicit owner authorization for this exact source
packet. Any change of backend, namespace, key length, source surface, or test
authority requires a revised preregistration.
