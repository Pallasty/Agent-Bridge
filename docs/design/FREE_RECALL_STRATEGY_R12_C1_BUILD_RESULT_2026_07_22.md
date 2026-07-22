# Free Recall Strategy R12 — C1 Build Result

Date: 2026-07-22

Status: **LOCAL BUILD PASS / INDEPENDENT LINUX PENDING / C1 NOT YET ACCEPTED**

Source receipt:
`docs/design/FREE_RECALL_STRATEGY_R11_C1_SOURCE_RECEIPT_2026_07_22.md`

## 1. Decision

The exact branch tip `59f8c1a3897e56f87c833eb4782a5712d5a96c0e` passes
the isolated C1 build and targeted tests locally. The required independent
Linux replay did not complete, so R12 does **not** accept C1 and does not open
C2.

This is a transport/toolchain blocker, not a source-test failure.

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

## 3. Independent Linux attempt

The intended aio2 replay could not obtain the exact source tree:

- aio2 is reachable and reports Linux x86_64, but has no existing
  `agent-bridge` checkout;
- public GitHub clone fails there because `github.com` cannot be resolved;
- standard SSH archive, SCP, and Tailscale File transfers stalled before a
  complete 10MB workspace bundle arrived. Observed partial limits were 4.8MB
  for the initial archive, 3,932,160 bytes for SCP, and 753,664 bytes for a
  2MB SCP fragment;
- the candidate fallback tb14 is reachable through Tailscale SSH and reports
  Linux x86_64, but has no `rustc`/`cargo` in PATH, `~/.cargo`, `/opt`, or
  `/usr/local`.

No remote Cargo command ran, no remote database was opened, and no remote
result is claimed. Incomplete aio2 transfer artifacts were never used as
source input.

## 4. Authority ledger

- C1 source: landed;
- local C1 feature check/tests: passed;
- independent Linux replay: pending;
- C1 acceptance: **false**;
- C2 store capability, trusted keys, runtime enablement, real producer event,
  retrieval, merge, release, and deployment: **closed**.

## 5. Next gate

One of these independent-infrastructure remedies is required before resuming
R12:

1. repair/restore aio2 source transport (Git DNS/connectivity or a reliable
   Tailscale/SSH file channel), then replay the exact `59f8c1a3` source after
   SHA-256 verification; or
2. separately authorize installing a fixed Rust/Cargo toolchain on tb14, then
   perform the same source-hash-verified Linux replay there.

Neither remedy opens C2. After an independent PASS, C1 can be accepted; only
then may a separate C2 design/authorization gate be considered.
