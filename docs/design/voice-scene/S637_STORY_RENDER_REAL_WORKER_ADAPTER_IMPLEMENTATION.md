# S637 Story render real Worker adapter implementation

## Status

Accepted as a source-only one-shot Worker implementation with synthetic
execution tests and one real process-protocol test. S637 closes
`B1_REAL_WORKER_ENTRYPOINT`: `scripts/story_render_one_shot_worker.py` now owns
the strict stdin/stdout process boundary selected by S620.

S637 does not make real rendering executable. The currently signed outer
protocol and the existing S604 executor contract bind different contract
digests and different output roots. The real path detects both conditions
before loading the installed-key composition and returns the fixed public error
`custody_rejected`.

No installed authority key was read, no nonce was consumed, no model session
was created, no output directory or audio was written, no audio was played, no
MCP surface or runtime configuration changed, and no artifact was deployed.

## Implemented process boundary

The Worker has two layers:

1. `process_request` receives already-bounded bytes plus the S620 contract,
   codec, and an execution callable. This is the dependency-injection boundary
   used by deterministic tests and by `main`.
2. `main` reads stdin once at `stdin_max_bytes + 1`, calls `process_request`,
   writes exactly one JSON document to stdout, flushes once, and exits zero
   after a protocol response has been emitted.

The default CLI loads SHA-256-pinned repository artifacts and uses
`execute_real`. It does not read environment variables, accept a CLI path,
spawn a shell, or launch a nested subprocess. Stderr stays silent; callers see
only S620-defined response codes.

Input decoding remains owned by `story_render_worker_protocol.py`. It rejects
oversize input, invalid UTF-8, non-object JSON, duplicate keys, non-finite
numbers, trailing documents, unknown fields, caller text/path fields, fixture
drift, request-identity drift, and malformed authorization shape.

## Fixed request construction

The process request contains no text, speaker, model, executable, script, or
arbitrary path. After decoding, `build_fixed_executor_request` derives the
private executor input only from pinned repository evidence:

- S602 supplies the accepted preflight digest, fixed selection count, and
  assembly gaps;
- S603 supplies the three accepted texts, speakers, styles, and cache keys;
- S604 supplies the bounded execution contract;
- S608 supplies the fixed CPU INT4 inference and model paths;
- the TTS support directory is the already-audited official CustomVoice
  snapshot.

Event identities are deterministic S620-local identifiers. Playback, recording,
and memory writing are unconditionally false. The output directory comes only
from the already shape-validated authorization envelope and must be the S620
private-root child named by the Supervisor request identity.

Every loaded JSON, codec, installed composition, and executor source is checked
against a fixed SHA-256 before decoding or execution. This is source drift
detection, not the immutable installation and descriptor-stable execution proof
required by S638.

## Real execution order

`execute_real` preserves this order:

```text
read pinned S604 contract
    -> compare outer authorization contract digest
    -> compare protocol and execution output roots
    -> build fixed executor request
    -> load installed-key composition
    -> prepare authority/model/nonce dependencies
    -> load bounded executor
    -> execute with current UTC time
    -> validate private receipt
    -> project bounded public response
```

The compatibility comparisons occur before the installed-key composition is
loaded. Once a later contract unifies the digest and output root, the existing
S613 composition becomes reachable only inside this real execution function.
The S606 executor still consumes the nonce before creating the output
directory, preserving the required post-nonce failure semantics.

## Current fail-closed incompatibility

The outer S620 envelope binds:

- contract SHA-256
  `be4bfc12d9adeda14b8d20048b91baaaf903f155a3fca5bd3413b2b649f7334d`;
- output root
  `/home/pallasting/.agent-bridge-secure/story-render/outputs`.

The current S604 executor binds:

- contract SHA-256
  `24edc82e885c7f8e5a934019e78530f0d70a482e15ec04c52824395fef1e0fe8`;
- output root
  `/Data/Models/agent-bridge/evidence/voice-scene/story-command-runtime`.

A single signed field cannot truthfully equal both contract digests, and the
legacy fuseblk root cannot satisfy the private output-custody contract. The
Worker therefore must not reinterpret, rewrite, or self-sign the envelope.
`custody_rejected` is the only truthful current real response.

The sanitized subprocess test invokes the actual script with a complete
shape-valid request. It exits zero, emits exactly one `custody_rejected`
document, and emits zero stderr bytes. The unit compatibility test replaces the
installed composition loader at the lowest external boundary and proves that
the loader is never reached.

## Public projection and redaction

A synthetic executor may return a realistic private S606 receipt containing
authorization identity, segment paths, assembly paths, gaps, and other internal
details. The Worker accepts a success only when:

- the receipt schema and status are the exact S606 values;
- playback and memory authorization are false;
- a non-empty segment array and assembly object are present;
- playback, recording, cache, and memory effects are false;
- the resulting public object passes the S620 response codec again.

The public success response contains only:

- protocol, request ID, status, render ID, and segment count;
- assembly SHA-256, sample rate, channels, frames, and duration;
- false playback and memory authorization.

Authorization IDs, MACs, nonces, absolute paths, private errors, and tracebacks
are never copied. Invalid request identity uses the fixed all-zero sentinel.
Known execution failures use only S620 codes. An unknown internal code,
unexpected exception, malformed receipt, forbidden effect, or projection
failure degrades to `internal_failure` without private detail.

## TDD evidence

The behavior suite contains ten tests. Each behavior was introduced with an
observed failing test before its implementation or tightening change:

- strict redacted success projection;
- malformed input rejection without executor invocation;
- typed public execution errors;
- invalid internal-code degradation;
- unexpected exception and malformed-receipt containment;
- forbidden runtime-effect rejection;
- one bounded stdin read and one stdout write;
- fixed repository-only executor request construction;
- pre-key current-contract rejection;
- the real sanitized subprocess response.

The final command is:

```text
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tests/test_story_render_one_shot_worker.py -v
```

It passes 10 tests with zero failures. `PYTHONDONTWRITEBYTECODE` keeps the
source-only test from leaving bytecode artifacts.

## Remaining blockers

S637 closes only B1. These remain open:

- B2: no product Guardian entrypoint;
- B3: the sealed plan does not yet bind immutable executable/script identity;
- B4: there is no owner-controlled Worker/Python package;
- B5: the execution and private output contracts have not converged;
- B6: there is no independent owner authorization broker;
- B7: `story_command_render` is not registered;
- B8: no trusted deployed binary/package or current-client adoption proof.

## Rollback

Rollback is deletion of the new Worker, test, and S637 artifacts. No live
configuration or process points at the script, GuardianV2 remains default-off,
and the installed Bridge remains unchanged. No output, nonce, or model state
requires cleanup.

## S638 gate

The next unit is `story_render_artifact_identity_and_python_package` under
source and isolated-package-test authority. It should bind the Worker,
Guardian, codec, composition, executor, and Python runtime to an immutable
manifest; prove POSIX owner/mode/link/parent custody; and select a fixed offline
Python dependency closure.

S638 may not read the installed authority key, load the model, create render
output, register MCP, enable runtime configuration, or deploy. Contract/output
convergence remains S640 work; package tests must continue to receive
`custody_rejected` from the real Worker path.
