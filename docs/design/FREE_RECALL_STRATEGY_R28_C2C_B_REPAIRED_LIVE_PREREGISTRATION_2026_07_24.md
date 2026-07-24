# Free Recall Strategy R28 — C2C-B Repaired Live Run Preregistration

Date: 2026-07-24

Status: **PREREGISTERED / ONE DISPOSABLE RUN ONLY**

Parent: R26 Attempt-1 (`INCOMPLETE`, no retry).

## 1. Purpose

R28 is a fresh experiment, not an R26 retry. It validates only the repaired
epoch/account binding in `7f3ccbf4`:

```text
active-epoch = c2c-live-<16 lowercase hex>
key account   = key:<the same epoch>
```

The previous mismatch wrote a bare hex active epoch beside a prefixed account,
so the accepted R25 reader could not derive the same item reference. R28 uses
new random material and a new temporary database; it never reuses an R26
account, directory, database, or output.

## 2. Fixed envelope

Build the current branch exactly with the default-off feature:

```text
cargo build -p ab-bridge --no-default-features \
  --features episode-observation-c2c-keychain-macos-live-lab \
  --bin agent-bridge --bin episode-observation-c2c-live-lab
```

The only permitted live invocation is:

```text
target/debug/episode-observation-c2c-live-lab \
  --agent-bridge "$PWD/target/debug/agent-bridge" \
  --execute-r26-live r26-c2c-live-authorized
```

The fixture creates one fresh `/tmp/ab-r26-c2c.XXXXXX/state.db` directory via
its tempdir helper. The directory is removed only after the in-memory receipt
has been validated. The Keychain service and sole two disposable accounts are:

```text
com.agent-bridge.episode-ref.v1
active-epoch
key:c2c-live-<16 lowercase hex>
```

No existing Keychain entry may be read beyond exact metadata-only absence
preflight for those two names. No source edit, merge, deployment, release,
Keychain enumeration, ACL/search-list change, or `security` shell command is
in scope.

## 3. Preflight gates

Before the one run, all must pass against `7f3ccbf4` or a descendant with no
R28-surface source change:

1. R27 source checker, including its directed mutations;
2. store fake-custody unit tests;
3. driver receipt unit tests;
4. default-feature-disabled bridge check;
5. a separate non-observation MCP preflight proving the fixed fixture text
   saves at least one core memory into an isolated temporary SQLite database.

## 4. Acceptance

Accept only if the driver emits a redacted receipt proving all of:

1. exactly one `curation_batch` episode;
2. one open, contiguous item positions starting at zero, and one close whose
   count equals the number of persisted core saves;
3. normal MCP process exit before the 30-second deadline;
4. exact Keychain cleanup and absence postchecks for both disposable accounts;
5. no raw memory key, account identifier, epoch, key material, child stderr,
   or backend error in the result.

Anything else is `INCOMPLETE`. A cleanup failure may report only the generated
public key-account identifier for exact recovery, then stops.

## 5. One-run rule

R28 permits exactly one live invocation. Whether it passes or fails, do not
retry it. A further run requires a separately numbered preregistration with a
new root-cause analysis and new explicit authorization.
