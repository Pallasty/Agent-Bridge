# Agent Runtime Interactive PTY Evidence Ledger

Date: 2026-06-30

This ledger records the current evidence boundary for `agent_spawn(interactive=true)`.
It is intentionally conservative: only runtimes with local PTY orchestration and a
verified or explicitly scoped submit profile are advertised as live interactive
backends.

## Current Contract

`agent_spawn(interactive=true)` is supported only for:

- `claude-code`: shared PTY helper, `SubmitProfile::ENTER`.
- `codex`: shared PTY helper, `SubmitProfile::KITTY_ENTER`; real Codex TUI verified.
- `kilo`: shared PTY helper, `SubmitProfile::ENTER`; real kilo TUI verified.
- `opencode`: shared PTY helper, `SubmitProfile::ENTER`; inferred from kilo and
  explicitly unverified until a real `opencode` binary is available.
- `gemini`: shared PTY helper, `SubmitProfile::ENTER_SETTLED`; real gemini TUI
  verified. gemini enables the Kitty keyboard protocol (like codex) yet submits
  on a bare CR — but its Ink input drops a zero-settle combined `text\r` write,
  so the CR is split off after a ~600ms render settle (a third submit shape,
  distinct from both `ENTER` and `KITTY_ENTER`).

Unsupported runtimes must reject `interactive=true` before spawning a process:

- `auggie`
- `warp-oz` / `oz`

## Local Availability Probe

Probe command:

```sh
for bin in opencode kilo gemini auggie oz warp; do command -v "$bin"; done
```

Result on this host:

- `kilo`: present at `/home/pallasting/.kilo/bin/kilo`, version `7.3.41`.
- `opencode`: not installed.
- `gemini`: installed (`@google/gemini-cli` v0.49.0, linked into `~/.local/bin`).
- `auggie`: not installed.
- `oz` / `warp`: not installed.

## Runtime Decisions

`opencode`: keep interactive support but label submit-key evidence as inferred.
The implementation must switch to `SubmitProfile::KITTY_ENTER` if a real opencode
TUI probe shows Kitty keyboard protocol behavior.

`gemini`: MIGRATED (2026-06-30). The Gemini CLI's Ink/React TUI was probed with a
real binary: it submits on a bare CR (NOT Kitty Enter, despite enabling the Kitty
keyboard protocol) but only when the CR is written separately from the text after
a render settle — hence `SubmitProfile::ENTER_SETTLED`. Auth uses a `GEMINI_API_KEY`
(the OAuth / Code Assist free tier was quota-exhausted); the operator's `~/.gemini`
needs `selectedType: "gemini-api-key"` to skip the first-run auth dialog headlessly.
Verified end-to-end by `tests/gemini_real_interactive.rs` (multi-turn 42/99).

`auggie`: migrate only when installed and real-binary tested. The current AB
runtime is the one-shot `auggie --print --quiet` wrapper; interactive mode must
not be advertised until the live TUI contract is verified.

`warp-oz` / `oz`: do not migrate to local PTY interactive mode. The runtime is a
cloud dispatch wrapper (`oz agent run-cloud`), where the local process posts a run
request and exits while the agent continues in Warp infrastructure. Follow-up
interaction belongs to Warp UI / `oz run` surfaces, not AB-owned PTY sessions.

## Guard Rails

Regression coverage added with this ledger:

- `agent_spawn_schema_exposes_interactive_flag` now asserts that the schema names
  `claude-code`, `codex`, `kilo`, `opencode`, and `gemini` as supported interactive
  backends (and does not name `auggie` / `warp-oz` / `oz`).
- `agent_spawn_interactive_rejects_non_pty_backends_before_spawn` registers
  missing-binary `auggie` and `oz` runtimes, then verifies `interactive=true`
  fails through the unsupported-interactive gate rather than reaching process spawn.

The runtime-specific tests still own real submit-key evidence:

- `tests/codex_real_interactive.rs` for Codex Kitty Enter.
- `tests/kilo_real_interactive.rs` for kilo bare Enter.
- `tests/gemini_real_interactive.rs` for gemini bare CR + render settle
  (`ENTER_SETTLED`); needs `GEMINI_API_KEY` and skips otherwise.

## Real-Binary Probe Harness

`crates/agent/tests/runtime_interactive_submit_probe.rs` provides a configurable
ignored probe for runtimes that are not yet installed or not yet migrated. It
uses the storage-free `PtySession` core directly, so it can test a CLI's raw TUI
submit behavior before that runtime is wired into `agent_spawn(interactive=true)`.

The probe is explicit opt-in: even with `--ignored`, it skips unless
`AB_REAL_PTY_PROBE_RUNTIME` or `AB_REAL_PTY_PROBE_BIN` is set.

Examples:

```sh
AB_REAL_PTY_PROBE_RUNTIME=opencode \
AB_REAL_PTY_PROBE_PROFILE=enter \
cargo test -p ab-agent --test runtime_interactive_submit_probe -- --ignored --nocapture

AB_REAL_PTY_PROBE_RUNTIME=gemini \
AB_REAL_PTY_PROBE_PROFILE=kitty_enter \
cargo test -p ab-agent --test runtime_interactive_submit_probe -- --ignored --nocapture
```

Useful overrides:

- `AB_REAL_PTY_PROBE_BIN=/absolute/path/to/cli`
- `AB_REAL_PTY_PROBE_ARGS_JSON='["--flag","value"]'`
- `AB_REAL_PTY_PROBE_CWD=/path/to/workspace`
- `AB_REAL_PTY_PROBE_BOOT_SECS=20`
- `AB_REAL_PTY_PROBE_RESPONSE_SECS=120`
- `AB_REAL_PTY_PROBE_PROMPT='Reply with exactly: AB42-PROBE-OK'`
- `AB_REAL_PTY_PROBE_EXPECT=AB42-PROBE-OK`

Operational rule: first run the probe with the suspected profile. If the TUI
accepts text but no marker returns, rerun with the other profile (`enter` vs
`kitty_enter`) before changing production `SubmitProfile` wiring.
