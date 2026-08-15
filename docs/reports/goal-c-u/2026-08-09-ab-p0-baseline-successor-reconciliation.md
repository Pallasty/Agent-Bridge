# Agent-Bridge P0 baseline and successor reconciliation

Date: 2026-08-09 (America/Los_Angeles)

Status: `P0_BASELINE_READY_SUCCESSOR_RECONCILIATION_REQUIRED`

## Decision

Do not continue either the Voice Projection VP5 successor or the local Qwen3-TTS
quantization experiment from the old mixed working tree.

Use the dual-remote common `master` commit
`bdb25189150d7015d8ef6eb2effe36093f402126` as the only clean integration
baseline. Preserve the old working tree byte-for-byte until its staged,
modified, and untracked assets have been assigned to an owner and lane.

The immediate successor is a reconciliation gate, not a runtime or model gate:

1. recover or explicitly supersede the Voice Projection VP5 predecessor claimed
   by forum thread 261 post 6012;
2. prove that predecessor is contained in the selected integration baseline;
3. only then preregister or implement its synthetic temporary-store replay
   successor;
4. keep the Qwen control-only stability experiment on an isolated research
   branch and port it onto the current worker contract before execution.

## Verified source state

- GitLab `master`: `bdb25189150d7015d8ef6eb2effe36093f402126`.
- GitHub `master`: `bdb25189150d7015d8ef6eb2effe36093f402126`.
- Clean reconciliation worktree:
  `/Users/pallasting/Projects/agent-bridge-p0-baseline-20260809`.
- Reconciliation branch: `codex/ab-p0-baseline-convergence-20260809`.
- The installed Agent-Bridge build reports source `75ffd49a3a17`; that commit is
  an ancestor of the common remote head and is two commits behind it.
- No deployment, restart, client refresh, model execution, audio output, or
  installed-state mutation was performed by this gate.

## Preserved old-worktree state

The original worktree remains at
`/Users/pallasting/Projects/agent-bridge`, `master@44a4b2d0`, with divergence
`+3/-314` relative to current `origin/master`.

Its three non-equivalent local commits are:

- `282567cc` — Worker contract compatibility probe;
- `adc40f68` — Sherpa-ONNX fallback;
- `44a4b2d0` — Qwen GGUF candidate gate.

The tree also contains staged, modified, and untracked work from multiple lanes.
Notable Qwen assets include `crates/qwen-quant`, activation and token-boundary
probes, fake-Q8 sensitivity tooling, frozen fixtures, tests, and result reports.
They are evidence-bearing research assets, but they are not current-main source
authority and must not be bulk-staged or rebased in place.

## Board-to-source discrepancy

Forum thread 261 post 6012 reports a VP5 source convergence commit
`2fd18b42` and names
`vp5_translation_replay_guard_atomic_commit_contract_synthetic_temp_store` as
its successor.

Fresh checks against both remote refs found:

- no ref containing `2fd18b42`;
- no `crates/bridge/src/meeting_projection.rs` at the common remote head;
- no current-main Voice Projection roadmap artifact named by the post.

Therefore the post is useful handoff evidence but not current source authority.
The successor remains `NOT_ADMITTED` until the predecessor is recovered and
contained, or the board record is explicitly superseded by a new decision bound
to current `master`.

## Two-lane plan

### Lane A — project mainline

Next gate: `VP5_PREDECESSOR_SOURCE_RECONCILIATION`.

Acceptance requires all of the following:

- exact predecessor commit or an auditable patch is available;
- its source, tests, contracts, and roadmap agree with post 6012;
- clean rebase or patch-equivalence onto the then-current dual-remote head;
- focused Voice Projection tests pass;
- board result records the integrated commit and explicitly retains the
  no-runner/no-model/no-audio/no-installed-nonce-DB boundary.

Only after this gate may the synthetic temporary-store atomic replay successor
start. The installed nonce database remains out of scope.

### Lane B — Qwen quantization research

Next gate remains the control-only stability envelope:

- one cold control run plus five warm control runs;
- no fake quantization and no model-file writing;
- finite log-space metrics and per-call input/output hashes;
- distinguish cold-start, warm-run, MPS/FP16, and restoration drift;
- defer Q3 packing and candidate promotion until the control envelope passes.

Before running it, port only the owned Qwen files into a dedicated branch based
on current `master`, review API drift against the current persistent worker, and
run the focused tests. The old mixed tree is evidence input, not the execution
surface.

## Rollback

This checkpoint is fully reversible: remove the new worktree and branch after
preserving any later commits. The original worktree, running Qwen worker, and
installed Agent-Bridge processes were not changed.
