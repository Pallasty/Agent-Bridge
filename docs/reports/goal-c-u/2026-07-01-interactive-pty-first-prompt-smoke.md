# Interactive PTY First-Prompt Smoke

Date: 2026-07-01
Host: `pallasting-ThinkBook-14-G5-IRH`
Worktree: `/Data/CascadeProjects/agent-bridge`
Scope: post-boot-settle evidence for `agent_spawn(interactive=true)` runtimes

## Why

Commit `2d1c873` added a boot-settle delay before the initial prompt is written
to real interactive TUIs. This report records the post-relink smoke and the
follow-up deterministic unit coverage that made the boot-settle contract visible
across every supported local interactive runtime.

The local evidence below was gathered before moving to the next lane.

## Environment

Binary availability on this host:

```text
codex=/home/pallasting/.local/bin/codex
claude=/home/pallasting/.local/bin/claude
claude-code=missing
gemini=/home/pallasting/.local/bin/gemini
kilo=/home/pallasting/.kilo/bin/kilo
opencode=/home/pallasting/.local/bin/opencode
```

Credential flags were checked without printing secret values:

```text
GEMINI_API_KEY=missing
OPENAI_API_KEY=missing
```

Codex still has local auth available through the installed CLI; its real TUI
test completed successfully.

## Verification

Initial-prompt regression across the runtime implementations:

```sh
cargo test -p ab-agent interactive_initial_prompt -- --nocapture
```

Result:

```text
running 8 tests
test claude_code::tests::interactive_initial_prompt_is_submitted_as_first_turn ... ok
test claude_code::tests::interactive_initial_prompt_waits_for_tui_boot_settle ... ok
test codex::tests::interactive_initial_prompt_is_submitted_as_first_turn ... ok
test codex::tests::interactive_initial_prompt_waits_for_tui_boot_settle ... ok
test gemini::tests::interactive_initial_prompt_is_submitted_as_first_turn ... ok
test gemini::tests::interactive_initial_prompt_waits_for_tui_boot_settle ... ok
test opencode_family::tests::interactive_initial_prompt_is_submitted_as_first_turn ... ok
test opencode_family::tests::interactive_initial_prompt_waits_for_tui_boot_settle ... ok
test result: ok. 8 passed; 0 failed
```

Follow-up commit:

```text
be3357a test(agent): cover initial prompt boot settle across runtimes
```

That commit adds deterministic delayed-ready stand-in tests for `claude-code`,
`codex`, and `gemini`, matching the already-existing `opencode_family` boot
settle test. The stand-in drains early stdin before printing `READY` and then
execs `cat`; the initial prompt must therefore be submitted after startup
settles, or it will be lost.

Full `ab-agent` validation after the follow-up:

```sh
cargo test -p ab-agent -- --nocapture
```

Result:

```text
running 74 tests
test result: ok. 74 passed; 0 failed
```

Claude Code PTY plumbing regression:

```sh
cargo test -p ab-agent claude_code::tests:: -- --nocapture
```

Result:

```text
running 5 tests
test claude_code::tests::send_input_rejected_without_interactive_session ... ok
test claude_code::tests::kill_unknown_session_errors ... ok
test claude_code::tests::interactive_session_multi_turn_round_trips ... ok
test claude_code::tests::interactive_args_are_passed_to_pty_child ... ok
test claude_code::tests::interactive_initial_prompt_is_submitted_as_first_turn ... ok
test result: ok. 5 passed; 0 failed
```

Real Codex TUI multi-turn smoke:

```sh
cargo test -p ab-agent --test codex_real_interactive -- --ignored --nocapture
```

Result:

```text
turn1 (expect 42): ROUND-TRIP OK
turn2 (expect 99): ROUND-TRIP OK
test codex_real_multi_turn_round_trip ... ok
test result: ok. 1 passed; 0 failed
```

Gemini real TUI smoke was attempted, but skipped because this shell has no
`GEMINI_API_KEY`:

```sh
cargo test -p ab-agent --test gemini_real_interactive -- --ignored --nocapture
```

Result:

```text
SKIP: set GEMINI_API_KEY to run the real gemini interactive test
test gemini_real_multi_turn_round_trip ... ok
test result: ok. 1 passed; 0 failed
```

The generic ignored submit-probe harness was also run without runtime overrides
to confirm it remains opt-in:

```sh
cargo test -p ab-agent --test runtime_interactive_submit_probe -- --ignored --nocapture
```

Result:

```text
SKIP: set AB_REAL_PTY_PROBE_RUNTIME or AB_REAL_PTY_PROBE_BIN to run the live probe
test configured_runtime_interactive_submit_profile_probe ... ok
test result: ok. 1 passed; 0 failed
```

Existing warnings during these runs were unchanged and unrelated:

- `ab-store` mixed-script warning for the test name
  `coactivation_stats_β_trigger_threshold`.
- `ab-store` dead-code warning for `vector_dim_for_model_name`.

## Boundary

This smoke records evidence only. It does not change runtime behavior, MCP tool
schemas, submit profiles, memory search, stored sessions, or installed binaries.

OpenCode and Kilo already had recent live smoke evidence in memory and session
history. Gemini remains pending a shell with `GEMINI_API_KEY`.
