# Free Recall Strategy R12 — C1 Build Result

Date: 2026-07-22

Status: **LOCAL BUILD PASS / INDEPENDENT LINUX PASS / C1 ACCEPTED**

Source receipt:
`docs/design/FREE_RECALL_STRATEGY_R11_C1_SOURCE_RECEIPT_2026_07_22.md`

## 1. Decision

The exact C1 source tip `59f8c1a3897e56f87c833eb4782a5712d5a96c0e` passes
the isolated C1 build and targeted tests locally and on independent Linux
node tb14. The source bundle was made from `e685b1da`, a docs-only descendant
of the C1 tip; R11's canonical C1 source-hash report remains unchanged and
passed on the local branch.

R12 therefore accepts C1. This acceptance does **not** open C2.

## 2. Local macOS evidence

Environment:

- `rustc 1.96.0 (ac68faa20 2026-05-25)`;
- `cargo 1.96.0 (30a34c682 2026-05-25)`;
- clean branch `codex/free-recall-strategy-r1` at exact tip `59f8c1a3`.

All commands used `--locked --offline`:

```text
cargo check -p ab-bridge --no-default-features \
  --features episode-observation-slice-c1 --locked --offline

cargo test -p ab-bridge --lib --no-default-features \
  --features episode-observation-slice-c1 \
  episode_observation_curation_batch --locked --offline

cargo test -p ab-bridge --lib --no-default-features \
  --features episode-observation-slice-c1 \
  session_curate_candidate_ledger --locked --offline
```

Results:

- feature-isolated `cargo check`: PASS;
- orchestration module: `4 passed, 0 failed`;
- candidate-ledger regression: `1 passed, 0 failed`;
- no C1-specific warning remains after explicit annotations for the intentionally
  inert error variants and injection setter.

The build still prints pre-existing warnings from `ab-store` and unrelated
`mcp_tools` dead-code/private-interface paths; none references the C1
orchestration module or its builder seam.

The R11 source checker was rerun after the final source tip: PASS, `14 / 14`
directed mutations rejected, report SHA-256
`37908892f8e5b8debbe0d76d33683618631ed5e0b31d00b4da97ead2158ff41a`.

## 3. Independent Linux replay — tb14

The aio2 transport attempt remains non-evidence: it could not receive a
complete source bundle. The independent replay was instead completed on
tb14 (Linux x86_64) after a private, fixed Rustup minimal-profile install.

Environment:

- `rustc 1.94.0 (4a4ef493e 2026-03-02)`;
- `cargo 1.94.0 (85eff7c80 2026-01-15)`;
- source bundle SHA-256:
  `39d1ca358021281fb8c537427cf33d2e20749d919d87c593d3d51f7aa5fe5252`;
- a missing compile-time fixture from the intentionally reduced source bundle
  was copied from the same local source and SHA-256 verified as
  `4d336f8884e3296e25dc4f8422a302a3df97e54ad343225b4b71fba996d3392e`.

Public dependencies were fetched only through `cargo fetch --locked`; the
acceptance replay itself used `--locked --offline`:

```text
cargo check -p ab-bridge --no-default-features \
  --features episode-observation-slice-c1 --locked --offline

cargo test -p ab-bridge --lib --no-default-features \
  --features episode-observation-slice-c1 \
  episode_observation_curation_batch --locked --offline

cargo test -p ab-bridge --lib --no-default-features \
  --features episode-observation-slice-c1 \
  session_curate_candidate_ledger --locked --offline
```

Results:

- feature-isolated `cargo check`: PASS;
- orchestration module: `4 passed, 0 failed`;
- candidate-ledger regression: `1 passed, 0 failed`.

The Linux build emitted the same unrelated `ab-store` mixed-script/dead-code
warnings and pre-existing `mcp_tools` private-interface/dead-code warnings;
no C1 source warning or failure occurred. No database was opened, no runtime
producer was enabled, and no deployment occurred.

## 4. Authority ledger

- C1 source: landed;
- local C1 feature check/tests: passed;
- independent Linux replay: passed on tb14;
- C1 acceptance: **true**;
- C2 store capability, trusted keys, runtime enablement, real producer event,
  retrieval, merge, release, and deployment: **closed**.

## 5. Next gate

C1 is closed. The next possible lane is a separate C2 design and authority
gate. It must define the narrow `StateStore` capability, trusted-key custody,
runtime enablement, and observation/retrieval boundaries before any C2 source
or runtime work begins.
