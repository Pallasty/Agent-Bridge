# Free Recall Strategy R30 — C2C-B Timeout Phase Probe

Date: 2026-07-24

Status: **PREREGISTERED / ONE DISPOSABLE RUN ONLY**

Parent: R28 (`INCOMPLETE`: timeout with no phase visibility) and R29 (accepted
source-only redacted timeout classifier).

## Goal

R30 does not attempt acceptance of the full C2C-B pipeline. It performs one
fresh disposable run solely to classify the highest completed MCP phase if the
process again exceeds the fixed 30-second deadline. A successful finalized
receipt is still recorded, but it is not required to justify the phase probe.

## Fixed envelope

Use the current branch at `fad295e9` or a descendant that changes no live-lab
source. Rebuild only the default-off driver and its separately invoked binary:

```text
cargo build -p ab-bridge --no-default-features \
  --features episode-observation-c2c-keychain-macos-live-lab \
  --bin agent-bridge --bin episode-observation-c2c-live-lab
```

Then invoke exactly once:

```text
target/debug/episode-observation-c2c-live-lab \
  --agent-bridge "$PWD/target/debug/agent-bridge" \
  --execute-r26-live r26-c2c-live-authorized
```

The custody, random account, temporary `/tmp` SQLite, cleanup, and no-output
restrictions are unchanged from R28. This run has fresh generated material;
it must not touch an R26/R28 account or database.

## Preconditions

The R27 static/mutation gate, store fake custody tests, driver unit tests,
default-feature-disabled check, and isolated non-observation MCP preflight
must all pass first.

## Result contract

On timeout, the only permitted diagnostic is one of:

```text
before_initialize_response
after_initialize_before_curate_response
after_curate_response_before_exit
```

The child is killed, waited, and its stdout reader joined before this label is
returned. No raw output or Keychain identifier is printed. Cleanup failure may
expose only the generated public account as already specified by R28.

## One-run rule

R30 permits one run only. Its result determines the next root-cause lane; it
must not be retried under this identifier.
