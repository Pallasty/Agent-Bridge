# S620 Story render one-shot worker protocol

## Status

Accepted as a static protocol contract. Worker implementation, MCP registration,
runtime enablement, execution, and deployment remain blocked.

## Context

S619 selected a one-process-per-render Python worker because process ownership
and rollback matter more than warm-model latency for the first single-user
fixture pilot. S620 turns that selection into a precise Rust supervisor/worker
boundary without spawning a worker or reading the installed authority key.

The host can have multiple Agent-Bridge MCP processes at once. An in-process
semaphore therefore cannot prove the S619 `max_active=1` claim across clients.
The protocol must also avoid inheriting S604's historical `fuseblk` output root
while retaining its accepted S602 fixture and model provenance.

## Decisions

### One bounded JSON exchange

The worker accepts exactly one strict UTF-8 JSON object and then EOF. It emits
exactly one JSON response and exits. Stdin and stdout are each capped at 64 KiB;
stderr is capped at 16 KiB and is never projected directly to MCP. Duplicate
keys, non-finite numbers, trailing data, unknown fields, and worker-spawned
subprocesses are forbidden.

The request contains only a supervisor-generated request/render identifier, the
fixed S602 fixture binding, and one closed S608 HMAC authorization envelope.
Callers cannot supply story text, source paths, model paths, output paths, or
playback/memory options. The envelope binds the S620 contract digest, fixed
preflight digest, and one private output child named by the render identifier.

### Host-wide reject-busy admission

Before requesting an owner grant, the Rust supervisor tries a non-blocking
exclusive `flock` on
`/home/pallasting/.agent-bridge-secure/story-render/render-worker.lock`. Busy
means no queue, no grant, no worker, and no nonce consumption. The descriptor is
held through worker reaping and response projection.

| Option | Benefit | Cost | Decision |
|---|---|---|---|
| Process-local semaphore | Minimal implementation | Does not coordinate multiple MCP processes | Reject |
| Durable render queue | Persistence and scheduling | Violates reject-busy and adds replay/state authority | Defer |
| Non-blocking POSIX file lock | Host-wide, releases on descriptor/process loss | Linux/POSIX-specific | Select |
| Transient service manager unit | Stronger service isolation | Adds service-manager and deployment surface | Defer |

### Owned worker termination

The supervisor uses absolute executable/script paths and no shell, creates a new
process group, writes once to stdin, closes it, and drains bounded stdout/stderr
concurrently. MCP cancellation, the 300-second deadline, or an I/O/protocol
limit triggers process-group `SIGTERM`, a two-second grace period, `SIGKILL`,
and mandatory `wait`. The direct worker also receives a parent-death `SIGKILL`;
it is forbidden to spawn child processes.

The host lock is not released until every spawned path has reaped the worker.
Any post-nonce failure requires a new owner grant; a grant reference is also
discarded after spawn failure even if its nonce was not consumed.

### Private custody and redaction

The legacy S604 execution contract is evidence for the fixed fixture and model
only. Its old output root is not admitted. S620 requires a `0700` root at
`/home/pallasting/.agent-bridge-secure/story-render/outputs`, `0700` job
directories, `0600` artifacts, no symlinks, and no replacement of an existing
target.

The worker reads the installed key and consumes the nonce before output
creation. Key bytes never enter the MCP process. Authorization ID, MAC, nonce,
key material, output directory, absolute paths, exceptions, and tracebacks are
forbidden from worker responses and MCP projections. A success projection may
contain only status, render ID, segment count, aggregate audio metadata, and the
explicitly false playback/memory authority flags.

## Accepted trade-offs

The protocol is Linux/POSIX-specific and reloads the model for every successful
grant. It also narrows the first runtime to the exact S602 chapter-two fixture.
Those costs are accepted to make concurrency, cancellation, secret lifetime,
output custody, and rollback mechanically reviewable before a broader `/story`
surface exists.

S620 does not create the lock or output root, issue a grant, read a key, consume
a nonce, spawn a process, load a model, render or play audio, write memory,
change configuration, or deploy a binary. The next gate is
`story_render_one_shot_worker_protocol_implementation_review`.
