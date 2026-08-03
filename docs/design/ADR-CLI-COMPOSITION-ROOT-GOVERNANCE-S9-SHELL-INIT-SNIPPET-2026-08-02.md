# ADR: CLI composition-root governance S9 ShellInit snippet mapping

## Status

Accepted for implementation on 2026-08-02.

- Base: `4e6fb29d7bf8b05e8dc8f5ea2225e90c4543012b`
- Coordination: Agent-Bridge forum thread #352
- Predecessor: S8 Avatar BackendProbe completed-result renderer, thread #350
- Scope: static `ShellKind` to OSC 133 snippet mapping only
- Adoption posture: source-only; no deployment, restart, or reconnect

## Context

After S8, `main.rs` still owns a pure `shell_init_snippet` function that maps
the three already parsed `ShellKind` variants to static strings. Its early
dispatch prints the returned string and exits before daemon, Store, Hub, file,
or terminal-runtime initialization. The function has no I/O and no fallible
operation.

This is a narrower seam than moving the ShellInit executor. Moving the executor
would also move stdout and early-return custody, while moving only the mapping
reduces physical concentration without hiding authority or changing behavior.

## Decision

Create private binary module `cli::shell_init` and move only
`shell_init_snippet` into it.

`main.rs` retains:

- the `Cmd::ShellInit` Clap schema and its help text;
- the `ShellKind` value enum and accepted values;
- early dispatch ordering;
- `print!`, stdout custody, SIGPIPE behavior, and `return Ok(())`.

`cli::shell_init` receives one copyable `ShellKind` and returns one static
string. Its `pub(crate)` visibility is needed for the private parent re-export;
the module remains private and exposes no library API.

## Behavior contract

S9 freezes exact real-binary contracts for:

- bash stdout bytes;
- zsh stdout bytes;
- fish stdout bytes;
- long-help stdout;
- invalid-shell exit code, empty stdout, and stderr;
- closed-consumer SIGPIPE behavior.

The first five contracts pass on unchanged base code. The ownership test then
fails only because `cli::shell_init` is absent, and both must pass after the
minimal move.

## Authority contract

The ownership test requires the composition root to retain schema, enum,
dispatch, print, and return custody. It forbids the private module from stdout,
filesystem, environment, Store, Hub, process, terminal-runtime, async, network,
or launchd authority.

S9 does not execute a shell, write an rc file, alter protocol bytes, create a
generic renderer framework, or authorize another command-family move.

## Documentation precision

The emitted snippets and installation instructions remain byte-for-byte
unchanged. The documentation source pointer changes from `main.rs` to
`cli/shell_init.rs` so it remains truthful after the ownership move.

## Stop and revisit conditions

Stop if extraction requires moving stdout/error/return ordering or acquiring
file, environment, Store, Hub, process, terminal-runtime, network, deployment,
or runtime authority. Any later ShellInit change requires its own behavioral
review; S9 authorizes only the static mapping move.

## Verification

Required before landing:

- exact CLI parity suite;
- S9 ownership/custody suite;
- existing SIGPIPE integration test;
- existing OSC 133 marker/doc-reference unit tests;
- adjacent CLI extraction boundary tests;
- scoped rustfmt and `git diff --check`;
- repository pre-commit all-target check;
- fresh `ab-bridge --all-targets` gate on reconciled master;
- non-force fast-forward and readback from both remotes.
