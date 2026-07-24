# Free Recall Strategy R19 — C2B Source Result

Date: 2026-07-23

Status: **LOCAL SOURCE PASS / LINUX PORTABILITY PASS / C2B SOURCE ACCEPTED / REAL CUSTODY UNVALIDATED / C2C CLOSED**

Source preregistration:
`docs/design/FREE_RECALL_STRATEGY_R18_C2B_MACOS_KEYCHAIN_SOURCE_PREREGISTRATION_2026_07_23.md`

## 1. Decision

The R18 macOS Keychain source packet is accepted. It adds one default-off,
macOS-targeted, store-private read adapter and no bridge or startup path.

This is source acceptance only. No test or command accessed the user's
Keychain, no key was generated or imported, and no runtime can currently call
the adapter. Real Keychain availability, prompt behavior, access control,
rotation, and revocation remain unvalidated.

## 2. Implemented boundary

- fixed Generic Password service `com.agent-bridge.episode-ref.v1`;
- fixed accounts `active-epoch` and `key:<epoch>`;
- public documented `generic_password(PasswordOptions)` read API only;
- exactly 32 key bytes;
- private buffers with explicit zeroization and `Drop` fallback;
- immediate Slice A derivation through a borrowed provider;
- payload-free custody errors;
- no environment, CLI, MCP, SQLite, bridge, logging, serialization, global
  cache, write API, or synthetic fallback;
- one crate-private entry reserved for a separate C2C packet.

The feature is absent from defaults. The module is also guarded by
`target_os = "macos"`.

## 3. Local macOS evidence

Commands:

```text
python3 scripts/eval/free_recall_strategy_r19_c2b_source.py
cargo check -p ab-store --no-default-features \
  --features episode-observation-c2-keychain-macos --locked --offline
cargo test -p ab-store --lib --no-default-features \
  --features episode-observation-c2-keychain-macos \
  episode_observation_c2_keychain_macos --locked --offline
cargo check -p ab-store --no-default-features --locked --offline
```

Results:

- source constraints: `18 / 18`;
- directed authority mutations rejected: `18 / 18`;
- macOS feature check: PASS;
- fake-reader custody tests: `5 passed, 0 failed`;
- default-off store check: PASS.

The tests cover successful derivation and zeroization, malformed/missing
custody inputs, short and long keys, epoch rotation, redacted backend/secret
sentinels, and zero reads under default construction. `MacOsKeychainReader`
is not instantiated by tests.

## 4. Independent Linux replay — tb14

Environment:

- `rustc 1.94.0 (4a4ef493e 2026-03-02)`;
- `cargo 1.94.0 (85eff7c80 2026-01-15)`.

The exact five source inputs were transferred to the isolated tb14 tree and
compared by SHA-256:

```text
3346d15ec2d17e45ed219b8e0aa02bdea1b72da03158af13170f7eeefee13d15  Cargo.lock
9cc32c1c8f1b4bf52561996e09677c47c4b546bbfbb33b019dadaad0b62accde  crates/store/Cargo.toml
050524f8dfa5dcb06400f1c570eed49bcf690263b986a3a82631baea830e0ff9  crates/store/src/lib.rs
aa3438e915fbb411979ebb20305ee8bbe21fba131ba0b09eb10574172c9c0b8c  crates/store/src/episode_observation_c2_keychain_macos.rs
4c7156d8b739f76e4940dc9dcc44bf6de7357f93a1c7d1d23314c07108eae0bc  scripts/eval/free_recall_strategy_r19_c2b_source.py
```

The final checker passed `18 / 18` constraints and `18 / 18` directed
mutations. The Linux `--locked --offline` feature check passed, proving target
isolation and absence of a non-macOS fallback. It does not prove Keychain
behavior.

## 5. Authority ledger

- C2A synthetic observation adapter: accepted;
- C2B macOS Keychain source: **accepted**;
- real Keychain access or custody validation: **closed**;
- key creation/import/rotation/revocation: **closed**;
- C2C runtime construction and observation: **closed**;
- bridge/MCP/retrieval/sync/export: **closed**;
- merge to master, release, and deployment: **closed**.

## 6. Next gate

The next possible lane is C2B-live custody validation, not C2C. It requires a
separate owner authorization that states:

1. whether a disposable Keychain entry may be created;
2. the exact temporary service/account namespace;
3. who creates and deletes it;
4. whether an OS access prompt is acceptable;
5. rollback and evidence handling;
6. confirmation that no production/user key or database is in scope.

Until that authorization exists, R19 is the terminal accepted state.
