# Free Recall Strategy R22 — C2C Runtime Enablement Preregistration

Date: 2026-07-23

Status: **DESIGN DECISION / R23 SOURCE NOT AUTHORIZED / STARTUP AND LIVE C2C CLOSED**

Parent acceptance:
`docs/design/FREE_RECALL_STRATEGY_R21_C2B_LIVE_KEYCHAIN_VALIDATION_RESULT_2026_07_23.md`

## 1. Goal

R22 defines the fail-closed assembly boundary between the accepted C1
`session_curate` producer, the accepted C2A store adapter, and a future
trusted C2B provider. It does not enable that path in any Agent-Bridge
process.

The next implementation packet, R23, is deliberately narrower than live
runtime wiring. It must first prove that an explicit authorization and every
required capability operand are necessary before the existing Hub injection
seam can receive an observation capability.

## 2. Existing accepted pieces

The repository already contains:

- the default-off C1 `CurationBatchObservationCapability` seam in `Hub`;
- the C1 controller that observes only successfully saved memories and
  suppresses close after an item failure;
- the default-off C2A synthetic store handle and bridge adapter;
- the C2B macOS Keychain reader, with one accepted disposable real-backend
  validation.

R22 therefore rejects a second controller, a second event schema, a public
provider interface, and bridge-owned key handling. C2C is an assembly and
activation problem, not a new observation model.

## 3. Canonical activation conjunction

An observation capability may be injected only when all five operands are
present:

```text
C1_COMPILED
AND C2_ADAPTER_COMPILED
AND EXPLICIT_RUNTIME_AUTHORIZATION
AND TRUSTED_PROVIDER_READY
AND CAPABILITY_ASSEMBLY_SUCCEEDED
```

The resulting truth table is strict:

| Missing operand | Hub observer | Observation events | Core curation |
| --- | --- | --- | --- |
| C1 feature | absent at compile time | zero | unchanged |
| C2 adapter feature | no constructor | zero | unchanged |
| explicit authorization | `None` | zero | unchanged |
| trusted provider | `None` | zero | unchanged |
| assembly success | `None` | zero | unchanged |
| none missing | injected capability | eligible, not guaranteed | unchanged |

“Eligible” is not a success claim. Begin, item, close, database, or custody
failure still follows C1's existing fail-closed sidecar behavior and must not
change the `session_curate` result.

## 4. Two-stage C2C boundary

### C2C-A — R23 structural assembly gate

R23 may add a crate-private assembler and synthetic tests only. Its runtime
authorization is an explicit typed value supplied directly by the test:

```rust
enum EpisodeObservationRuntimeAuthorization {
    Disabled,
    ExplicitSyntheticLab,
}
```

There is no default conversion to `ExplicitSyntheticLab`. The assembler
accepts the authorization plus an optional already-constructed capability and
returns `None` unless both are present. It does not construct a provider,
open a database, read configuration, or touch Keychain.

This stage proves the conjunction and Hub injection semantics without
creating a production activation path.

### C2C-B — separately authorized startup wiring

Only after R23 acceptance may a later packet propose:

- one explicit CLI activation value;
- one platform-fixed Keychain-backed store constructor;
- one normal-process `build_hub` injection;
- one bounded disposable-database runtime run.

The future activation value must be explicit command-line configuration, not
an environment variable, MCP argument, database value, or implicit Keychain
presence check. Backend selection is fixed by the compiled feature and target;
the CLI may authorize observation but may not select a secret service, name
an account, or carry key material.

R22 does not select the final CLI spelling and grants no C2C-B source
authority.

## 5. Exact proposed R23 source surface

| Path | Purpose |
| --- | --- |
| `crates/bridge/Cargo.toml` | Add one default-off `episode-observation-c2c-runtime-assembly-synthetic` feature depending only on the accepted bridge C2 synthetic feature. |
| `crates/bridge/src/lib.rs` | Declare the R23 module under that feature only. |
| `crates/bridge/src/episode_observation_c2c_runtime_assembly_synthetic.rs` | Typed authorization, pure fail-closed assembler, and disposable synthetic tests. |
| `scripts/eval/free_recall_strategy_r23_c2c_runtime_assembly_source.py` | Reject startup, configuration, custody, public API, and authority expansion. |

R23 must not modify:

- `crates/bridge/src/main.rs`;
- `crates/bridge/src/hub.rs`;
- `crates/bridge/src/mcp_tools.rs`;
- the C1 controller or C2A adapter;
- any `ab-store` source or feature;
- schema, migration, retrieval, sync/export, MCP/API, setup, hooks, release, or
  deployment files.

The existing crate-private `HubBuilder::curation_batch_observer` is the only
admissible injection seam. R23 tests may call it; R23 source may not widen its
visibility.

## 6. R23 structural contract

The assembler must:

1. receive a typed authorization value;
2. receive `Option<Arc<dyn CurationBatchObservationCapability>>`;
3. return `None` for disabled authorization;
4. return `None` for a missing capability;
5. return the same opaque capability only for explicit synthetic-lab
   authorization plus a present capability;
6. never inspect the capability, store, key provider, database, or event;
7. expose no public constructor and perform no I/O.

The authorization type and assembler remain crate-private. They must not be
re-exported by `ab_bridge`, accepted as MCP/JSON input, or inferred from
feature presence.

## 7. Required R23 falsifiers

R23 acceptance requires disposable synthetic tests for:

1. feature absent: the normal no-feature build has no C2C module or injection;
2. authorization disabled + capability present: zero observation rows;
3. authorization explicit + capability absent: zero observation rows;
4. authorization disabled + capability absent: zero observation rows;
5. authorization explicit + capability present: one bounded
   open → item → close finalized synthetic episode;
6. begin failure: no finalized episode and core memory save succeeds;
7. item failure: no finalized episode and later close is suppressed;
8. close failure: no finalized episode and core curation result is unchanged;
9. no candidates or no successful saves: no finalized episode;
10. the observer remains absent from a normally built `Hub`.

Tests must use a disposable SQLite database and the accepted deterministic
synthetic provider only. They may not read Keychain or create a persistent
entry.

## 8. Static rejection gate

The R23 checker must reject:

- adding the R23 feature to any default feature set;
- `main.rs`, setup, hook, deploy, or MCP registry changes;
- `std::env`, Clap, JSON, SQLite, filesystem, Keychain, security-framework,
  or network reads in the assembler;
- a boolean/string authorization with an implicit true/default;
- construction of a provider or synthetic key in the bridge assembler;
- public visibility, re-export, `StateStore` widening, or a new Hub field;
- direct event append/projection calls;
- bridge access to epoch, account, key bytes, custody errors, or backend
  errors;
- activation inferred from feature compilation or capability presence alone.

Directed mutations must separately remove each conjunction operand and prove
that the checker or tests fail.

## 9. Proposed R23 acceptance commands

```text
python3 scripts/eval/free_recall_strategy_r23_c2c_runtime_assembly_source.py

cargo check -p ab-bridge --no-default-features --locked

cargo test -p ab-bridge --lib --no-default-features \
  --features episode-observation-c2c-runtime-assembly-synthetic \
  episode_observation_c2c_runtime_assembly_synthetic \
  --locked --offline

cargo test -p ab-bridge --lib --no-default-features \
  --features episode-observation-c2c-runtime-assembly-synthetic \
  episode_observation_curation_batch \
  --locked --offline
```

An independent Linux `--locked --offline` replay is required before R23
acceptance. R23 is not accepted from source inspection or local macOS tests
alone.

## 10. Negative authority

R22 authorizes this design document only. It authorizes no R23 source, real
Keychain access, persistent key, provider construction, user database,
`main.rs` wiring, CLI/config flag, normal-process observation, retrieval,
sync/export, MCP/API exposure, merge to master, release, deployment, training,
or BioCortex integration.

The next valid action is explicit owner authorization for the exact R23
source surface and tests in §§5–9. C2C-B remains closed even if R23 passes.
