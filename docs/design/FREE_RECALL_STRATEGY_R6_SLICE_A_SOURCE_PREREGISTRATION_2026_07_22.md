# Free Recall Strategy R6 — Slice A Source Preregistration

Date: 2026-07-22

Status: **AUTHORIZED SOURCE ONLY / DEFAULT-OFF / NO BUILD OR EXECUTION AUTHORITY**

Parent result:
`docs/design/FREE_RECALL_STRATEGY_R5_SOURCE_ONLY_PLAN_RESULT_2026_07_22.md`

## 1. Authorized source

R6 Slice A may add only:

- one private `ab-store` module behind a new default-off
  `episode-observation-slice-a` feature;
- pure event/source contract types;
- the R5 HMAC-SHA-256 `item_ref` derivation and validation boundary;
- an internal borrowed key-provider interface;
- a synthetic provider inside unit tests only;
- a no-op sink that always reports disabled and performs no I/O;
- public-synthetic known-answer and directed failure tests.

The feature reuses the already-declared optional `ring = 0.17` dependency.
R6 does not add a crate, enable the feature by default, or couple it to the
existing temporal-evidence features.

## 2. Source invariants

- no type derives serialization for key material;
- no key material implements `Clone` or `Debug`;
- keys are borrowed, at least 32 bytes, and never copied into an output;
- active derivation obtains epoch and key together from the provider;
- epoch lookup accepts only provider-known epochs and otherwise abstains;
- epoch grammar and memory-key byte bounds match R5 exactly;
- HMAC authenticates independently length-framed domain, epoch, and exact key;
- output is full 32-byte lowercase hexadecimal digest;
- no-op sink cannot mutate, persist, log, emit telemetry, or claim success;
- the module imports no SQLite, filesystem, environment, MCP, network, clock,
  retrieval, sync, export, or BioCortex surface.

## 3. Static gates

Because build and test execution are not authorized, this lane may run only:

- `rustfmt` on the exact new Rust file;
- textual checks for the feature's default-off isolation and forbidden imports;
- `git diff --check` and source review;
- the previously authorized Python R5 validator.

Unit tests are source artifacts, not passing evidence. A later build gate must
run them locally and independently on tb14 before Slice A can be accepted.

## 4. Stop conditions

Stop before Cargo metadata resolution, check, build, test, SQLite work,
production provider work, producer wiring, real data, merge, or deployment.

If the existing `ring` API cannot express the frozen contract without changing
dependencies, stop and request a named dependency authorization.
