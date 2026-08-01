# S5ZN Rust story registration review

## Outcome

The native story preflight is not admitted for MCP registration yet. S5ZM
proves value parity, but registration would turn a pure library function into
an externally reachable file-reading operation. The selected path is to harden
the native adapter before touching the module tree or tool registry.

## Evidence-based blockers

1. Source admission is not bounded. The current reader validates suffix and
   UTF-8, but accepts an arbitrary path and has no fixed byte ceiling.
2. Runtime evidence resolution is absent. The native composition requires
   accepted voice-plan, mapping, role-acceptance, and continuity values; the
   proposed MCP input does not supply them and no configured resolver exists.
3. Async cancellation ownership is absent. The source reader performs
   synchronous filesystem work and there is no contract guaranteeing that
   caller cancellation stops owned blocking work.

The review builder derives these blockers from source markers, binds the
current registry, library, native module, and S5ZM receipt hashes, and fails on
a tool-name collision or invalid parity authority.

## Retained surface contract

The future tool remains `story_command_preflight`, `Niche`, absent from the
default, codex-essential, and codex-voice sets. Its explicit activation gate is
`AB_STORY_COMMAND_PREFLIGHT_ENABLE=1`. These are proposed properties, not a
registered or deployed capability.

## Scope

S5ZN does not export `story_contract`, edit the Rust registry, register a tool,
load a model, execute ONNX, render or play audio, or write cache/memory. The
next gate is `rust_story_preflight_adapter_hardening`.
