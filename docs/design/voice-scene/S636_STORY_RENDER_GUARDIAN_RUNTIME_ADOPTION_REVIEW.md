# S636 Story render Guardian runtime-adoption review

## Decision

Runtime adoption is blocked. The Qwen3-TTS model assets are present and the
complete S608 CPU INT4 bundle still matches its recorded hashes, so another
model download is not required. The missing work is the authority-bearing
execution shell around those assets: there is no real one-shot Worker
entrypoint, no product Guardian entrypoint, no immutable Worker/Python package,
no file-identity binding, no secure output contract, no owner-envelope broker,
no render MCP surface, and no trustworthy deployed artifact containing S635.

S636 is a review-only gate. It does not execute the real Worker, read the
installed signing key, create an authorization envelope, load a model, write or
play audio, register an MCP tool, modify runtime configuration, restart a
process, or deploy a binary.

The next bounded unit is S637,
`story_render_real_worker_adapter_implementation`. S637 may implement and test
the missing one-shot protocol adapter against injected synthetic dependencies.
It may not touch the installed key, model, audio device, MCP registry, or
deployment path.

## Evidence layers

The decision deliberately keeps five evidence layers separate:

1. **Source:** S635 implements ABG2, GuardianV2, last-close lock custody,
   bounded asynchronous streams, and cleanup proofs. `DirectV1` remains the
   constructor default.
2. **Model files:** the official CustomVoice snapshot and the community CPU
   INT4 snapshot are present. The S608 verifier streamed and matched the full
   community ONNX bundle on 2026-08-02 without importing the inference module
   or creating a model session.
3. **Installed binary:** `agent-bridge.real` is at `78301b1d72c4`, fourteen
   commits behind the reviewed source, and does not contain S635.
4. **Live MCP processes:** health is generally good, but the observed set
   included eleven current-inode MCP processes and two stale-inode MCP
   processes. This is process freshness evidence, not Story render adoption.
5. **Current client:** the client directly invoked
   `story_command_preflight`, including the fixed chapter-two fixture, and
   received a dry-run result with execution unauthorized. The current client
   exposes no `story_command_render` tool.

`doctor ok=true` is not promoted into a Story render claim. It does not prove a
Guardian entrypoint, Worker package, current-client render registration, model
execution, or human audibility.

## What S635 actually provides

S635 is a strong custody primitive, not a runnable product path:

- `StoryRenderCustodyMode::GuardianV2` is explicitly injected and default-off;
- `run_guardian_entrypoint` understands Guardian and bootstrap roles;
- a sealed memfd transports a canonical path/argument/environment plan;
- the Host validates the exact Guardian, Worker PID/PGID, and plan digest before
  payload start;
- Host-owned bounded sockets carry Worker stdin/stdout/stderr;
- the Guardian and Host retain shared last-close custody of the render lock;
- exact reaping and process-group absence precede a clean terminal result;
- the synthetic fault matrix covers Host EOF, Guardian loss, residual
  descendants, descriptor leakage, bounded output, malformed responses, and
  DirectV1 regression.

No product `main`, CLI role, dedicated binary, MCP handler, package script, or
deployment step calls that entrypoint. Searching the product source finds only
synthetic compositions configuring GuardianV2. Therefore S635 remains truthful
synthetic evidence.

## Actual render chain

The existing Python render components are useful but do not yet form the S620
Worker process:

```text
story_command_preflight (read-only MCP)
    -> deterministic chapter/segment plan
    -> execution_authorized=false

future story_command_render
    -> owner envelope ingress                       [absent]
    -> Guardian product entrypoint                  [absent]
    -> strict one-shot Worker protocol entrypoint   [absent]
    -> installed-key secure composition             [callable exists]
    -> bounded render executor                       [callable exists]
    -> trusted ONNX runner                           [source exists]
    -> Qwen3-TTS community CPU INT4 model            [present and hash-valid]
    -> private secure output root                    [absent/incompatible]
```

`story_render_worker_protocol.py` already supplies the strict codecs.
`story_bounded_render_executor.py` supplies an in-process bounded executor, and
the S609-S616 composition supplies model, nonce, and installed-key validation.
But `scripts/story_render_one_shot_worker.py`, selected by S620, does not exist.
The executor cannot be passed directly as the Guardian script because it has no
one-request/one-response process entrypoint and its receipt needs a public
redaction projection.

## Model and Python compatibility

The model is not the adoption blocker.

- Official original snapshot:
  `/4TNVMe2/aiot_weights/modelscope/models/Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice/snapshots/master`
- Community ONNX CPU INT4 snapshot:
  `/4TNVMe2/aiot_weights/modelscope/models/onnx-community--Qwen3-TTS-12Hz-1.7B-CustomVoice/snapshots/master/cpu_int4`
- S608 full bundle hash verification: passed in 9.909 seconds.
- Model sessions or graph execution in S636: none.

The S635 synthetic plan uses `/usr/bin/python3`. Under the exact sanitized
environment relevant to a Worker launch, that interpreter lacks `numpy`,
`onnxruntime`, `soundfile`, `transformers`, and `torch`. A real plan therefore
needs an absolute executable in a fixed, offline dependency environment. It
cannot inherit the interactive shell, user site packages, `PATH`, or a mutable
source checkout.

## Eight blocking conditions

### B1 — real Worker entrypoint

The S620-selected one-shot Worker is absent. S637 must add exactly one bounded
stdin request and one bounded stdout response, reject trailing data, project a
redacted public response, and convert all failures into the existing stable
protocol codes. Diagnostics may use bounded stderr but must not contain key,
envelope, nonce, text, model path, or private output details.

### B2 — product Guardian entrypoint

`run_guardian_entrypoint` has no product caller. A dedicated minimal Guardian
executable is preferred over the general `agent-bridge` wrapper: the current
wrapper sources broad credentials before executing `.real`, which is
incompatible with the least-authority render process. Role dispatch must occur
before normal Bridge initialization.

### B3 — executable identity and TOCTOU

`WorkerExecPlanV1` seals the encoded plan, but the plan currently authenticates
path strings rather than the bytes and custody of the executable and script.
Configuration validation checks that the script is a file; it does not bind
hash, device/inode, owner, mode, link count, parent-directory custody, or a
descriptor-stable execution object. This is a critical authority boundary: a
sealed instruction to execute a replaceable path is not an immutable launch.

S638 must introduce a hash-bound installation manifest and POSIX ownership/mode
checks. The launch must either execute a verified stable descriptor or prove
that the verified identity cannot change between verification and `exec`.

### B4 — immutable package and fixed Python

`deploy_from_master.sh` installs the general Bridge binary and audio adapter.
It does not install the Guardian, Worker, codec, secure composition, trusted
runner, or a Python dependency closure. S638 must package only the required
files into owner-controlled POSIX custody and bind their hashes. Network access
and dependency resolution remain prohibited at runtime.

### B5 — secure output root

The existing S604 execution contract binds a legacy output root on fuseblk.
S620 requires
`/home/pallasting/.agent-bridge-secure/story-render/outputs`, but that directory
does not currently exist. The contracts must converge on the private ext4 root,
created with owner-only custody, before a real render.

### B6 — owner authorization broker

A previous fixed render proved that a short-lived owner-signed envelope can be
validated and consumed. There is no runtime ingress that obtains a new owner
decision while keeping the installed key and envelope out of the MCP process.
The broker must be separate, explicit, single-use, expiry-bounded, and scoped to
the exact preflight digest and fixture.

### B7 — render MCP surface

Only `story_command_preflight` is registered. Its schema requires
`dry_run=true`, its annotations are read-only, and its result explicitly denies
execution. The future render adapter stays default-off until B1-B6 close. The
MCP process must never read the installed authority key.

### B8 — deployed artifact and install trust

The installed `.real` binary is fourteen commits behind S635. It is observed as
root-owned mode `0777` on fuseblk, while the secure runtime root is owner-owned
mode `0700` on ext4. FUSE permission reporting can reflect mount semantics, but
it cannot establish the POSIX immutability required for an authority-bearing
Worker. The current credential-injecting wrapper is also the wrong launch
boundary. S642 must review a separate secure install and fresh-client adoption;
this review does not deploy it.

## Selected implementation ladder

The blockers should close in dependency order:

1. **S637 — real Worker adapter implementation.** Add the missing source-only
   adapter and injected synthetic tests. No key, model, output, registration,
   or deployment.
2. **S638 — artifact identity and Python package.** Bind hashes and POSIX
   custody, create a fixed offline Python environment, and prove descriptor or
   identity stability using only isolated package tests.
3. **S639 — Guardian product entrypoint.** Add the minimal dedicated role
   dispatcher and synthetic process tests; keep product runtime default-off.
4. **S640 — secure output and owner broker.** Converge the output contract and
   prove envelope delivery with synthetic authority material only.
5. **S641 — default-off render registration.** Add the MCP adapter and verify a
   fresh client can see and reject/dry-run it without executing the Worker.
6. **S642 — deployment-adoption review.** Re-check source, package, installed
   files, process freshness, client tool list, and rollback before enablement.
7. **S643 — single authorized fixture pilot.** With a separately granted exact
   owner envelope, run one fixed fixture. Playback remains a separate audibility
   gate.

This ordering prevents packaging work from legitimizing an incomplete Worker,
prevents MCP registration from becoming implicit execution authority, and
prevents the already-downloaded model from being mistaken for a safe runtime.

## Rollback and authority

S636 has no runtime rollback because it made no runtime change. GuardianV2
remains default-off; `DirectV1` remains the source default; no installed process
was restarted; and no client configuration was changed.

Future source and isolated-package stages are reversible. Any later installed
key access, owner envelope issuance, real model execution, runtime enablement,
deployment, or playback must satisfy its own explicit gate. Recoverability does
not collapse these distinct authorities.

## Nonclaims

S636 does not prove real Worker/Guardian compatibility, Python dependency
closure, executable identity stability, secure output custody, owner-envelope
delivery, Qwen3-TTS execution, audio quality, MCP render visibility, deployed
binary adoption, simultaneous Host and Guardian loss, cgroup/systemd custody,
or human audibility.

## S637 gate

S637 may add `scripts/story_render_one_shot_worker.py` and focused tests around
the already-defined S620 codec and bounded executor seam. Acceptance requires:

- exactly one bounded request and one bounded public response;
- dependency injection for synthetic success/failure tests;
- no import-time model or key access;
- no caller-controlled executable, script, model, output root, or free-form
  path;
- installed-key composition reachable only inside the real execution function;
- nonce-before-output ordering preserved by the existing executor;
- no authority identifier or sensitive diagnostic in stdout/stderr;
- no MCP registration, runtime configuration, deployment, model load, audio
  write, or playback.

Closing B1 will not authorize S638 or any runtime action; it only produces the
missing protocol-compatible process boundary for subsequent identity and
packaging work.
