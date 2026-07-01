# Kilo First-Prompt Readiness Verification - 2026-07-01

## Scope

Verify landed commit:

- `66c93df fix(agent): wait for kilo first prompt readiness`

Current branch state at verification time:

- `HEAD = origin/master = 66c93df`
- working tree clean before report creation

This verification covers deterministic local tests only. It does not run the
ignored real-binary kilo network tests.

## Change Summary

The commit adds a readiness-marker path to the shared interactive PTY helper:

- `SubmitProfile` can now carry `initial_prompt_ready_markers` and
  `initial_prompt_ready_timeout`.
- `spawn_interactive` waits for a configured marker before submitting the
  optional first prompt.
- kilo uses the visible composer marker `Ask anything` with a 30 second timeout.
- opencode keeps its existing fixed initial prompt delay.

The commit also tightens `agent_session_reconcile`:

- untracked sessions are deferred by default;
- `dry_run=false` still requires `apply_confirmation`;
- finalising untracked sessions additionally requires
  `finalise_untracked=true` and
  `apply_untracked_confirmation="finalise_untracked_sessions"`.

## Verification

Effective local checks:

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-agent initial_prompt_waits_for_ready_marker_before_submit -- --nocapture
```

Passed: 1/1. This directly exercises the readiness-marker wait path.

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-agent interactive_initial_prompt -- --nocapture
```

Passed: 8/8. This keeps the existing initial-prompt behavior green for
claude-code, codex, gemini, and the opencode/kilo family.

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-agent -- --nocapture
```

Passed: 75/75 plus non-ignored integration/parser tests. Ignored real-binary
tests remained ignored.

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-bridge --no-default-features agent_session_reconcile_defers_untracked_sessions_by_default -- --nocapture
```

Passed: 1/1. This verifies the new untracked-session confirmation gate.

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-bridge --no-default-features agent_session_reconcile -- --nocapture
```

Passed: 1/1 with the same reconcile target under the broader name filter.

Compilation-only / ignored-test boundary check:

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-agent --test kilo_real_interactive -- --nocapture
```

Result: 0 passed, 0 failed, 2 ignored. This confirms the real-binary kilo test
target compiles and remains opt-in; it is not live behavioral evidence.

Known warnings observed during these runs were pre-existing compiler warnings,
including mixed-script confusables in `ab-store`, private-interface warnings in
`ab-bridge`, and dead-code warnings for disabled surfaces. No new failure was
observed.

## Decision

Treat `66c93df` as locally verified for deterministic coverage.

The remaining live proof, if needed, is explicitly owner/operator gated:

```text
cargo test -p ab-agent --test kilo_real_interactive -- --ignored --nocapture
```

That command may drive a real kilo CLI and provider path, so it was not run in
this verification slice.

## Boundary

This report does not change runtime behavior, enable new deployment flags, run
live kilo/opencode provider calls, finalise real sessions, or change stored
session rows. It records deterministic verification for an already-landed
commit.
