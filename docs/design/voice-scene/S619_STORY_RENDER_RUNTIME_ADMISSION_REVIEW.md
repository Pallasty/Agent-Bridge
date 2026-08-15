# S619 Story render runtime admission review

## Status

Accepted as a blocking architecture decision. Current render-runtime wiring and
deployment are not admitted.

## Context

S618 proved that the bounded Qwen3-TTS output has exactly the PCM content already
accepted by the owner. The current installed `codex-voice` MCP surface also
exposes one live, read-only `story_command_preflight` tool whose schema forces
`dry_run=true`. That does not make the separate Python renderer safe to expose.

The reviewed system is a single-host, owner-operated fixture pilot. Correct
cancellation, authority custody, private output, and rollback are prioritized
over warm-model throughput. Arbitrary novel paths, playback, recording, and AB
memory integration remain later capabilities.

## Current admission decision

Direct wiring is blocked by seven conditions:

1. No Story render MCP surface or worker protocol exists.
2. The installed-key composition is not an explicit owner-approval broker.
3. The synchronous Python runner has no cooperative cancellation parameter.
4. There is no single-job admission gate or reject-busy rule.
5. S617 audio was retained on a `fuseblk` path with observed `0777` semantics.
6. No MCP projection removes the executor receipt's authorization identifier.
7. The installed binary is 25 commits behind the reviewed dual-remote source.

The existing preflight cancellation path is sound for its current purpose: MCP
cancellation aborts the tool future, the drop guard cancels the shared token,
and the owned blocking preflight worker is joined. Those guarantees do not
extend to Qwen inference because the renderer is a separate synchronous Python
path and is not called by the Rust adapter.

## Options considered

| Option | Benefit | Cost | Decision |
|---|---|---|---|
| Port the complete runner into Rust | One runtime and native ownership | New tokenizer and ONNX inference port; highest validation scope | Defer |
| Long-lived Python worker | Warm model and lower repeated latency | Durable state, restart, secret-lifetime, and multiplexing complexity | Defer |
| One-shot supervised Python worker | Strong kill/reap isolation and simple rollback | Reload model for each authorized render | Select for S620 |

## Selected next architecture

S620 should define, but not yet deploy, `story_command_render` as a default-off
Niche tool gated by `AB_STORY_COMMAND_RENDER_ENABLE=1`. One explicit owner grant
starts at most one worker; concurrent calls fail busy instead of queuing. Rust
owns a supervisor that sends a length-bounded JSON request over stdin without a
shell, provides an allowlisted environment, enforces a 300-second deadline, and
kills and reaps the worker process group when the MCP future is cancelled.

The MCP process never receives key bytes. The worker reads the installed key,
verifies the owner envelope, consumes its single-use nonce, and writes only
under `/home/pallasting/.agent-bridge-secure/story-render/outputs` with a `0700`
root. MCP receives only a redacted projection: no authorization ID, MAC, nonce,
or key material.

The first contract remains bound to the already accepted S602 fixture preflight.
It does not admit arbitrary novel paths, playback, recording, cache writes, or
memory writes.

## Trade-offs and consequences

The selected design deliberately pays model startup latency on every trial.
That is acceptable while calls are rare and single-user because process-level
cancellation and minimal retained state are more valuable than throughput.
Revisit a long-lived worker only after repeated accepted trials demonstrate
that reload latency is the dominant usability constraint and the worker can be
given an equally strong restart, secret, and job-isolation contract.

No binary, wrapper, configuration, client, nonce, model, audio, or AB memory was
changed by S619. Its next gate is
`story_render_one_shot_worker_protocol_contract`.
