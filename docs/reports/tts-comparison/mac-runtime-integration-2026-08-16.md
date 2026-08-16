# OmniVoice Mac runtime integration — 2026-08-16

## Decision

The Mac remote execution path is technically ready for the existing bounded
OmniVoice canary. It remains default-off. This validation does not authorize a
production-default change, a canary-percentage increase, or removal of Qwen3.

## Validated composition

- Runtime: Python 3.12, ONNX Runtime 1.28.0 on arm64 macOS
- Graphs: FP16 embeddings, FP32 bidirectional LLM and heads, FP16 decoder
- Decode steps: 32
- Output: mono PCM WAV at 24 kHz
- Component SHA-256 and byte sizes: verified from the node-local composition
  manifest before every synthesis

The node-local manifest contains machine paths and is deliberately not checked
into the repository.

## Results

| Gate | Result |
| --- | --- |
| Focused Python regression suite | 86 passed |
| Direct Mac adapter synthesis | passed; RTF 2.66 |
| SSH worker, WAV copy, and cleanup | passed; RTF 2.70 |
| `audio_embody.synth_omnivoice` entry | passed; RTF 2.58 |
| Checked-in 10% canary success route | bucket 747; assigned/executed `omnivoice` |
| Missing-manifest fault injection | assigned `omnivoice`; executed `qwen3`; fallback true |
| Qwen3 fallback WAV | passed; 1.7B CustomVoice, Serena, CPU float32, 24 kHz |

The successful cross-node artifact was 2.36 seconds, 113,324 bytes, with
SHA-256 `9ddf689f531f35921d53a12b9c465ebfb64b918a74aaa9dd8fdddcc29ba451bc`.
The UUID-scoped remote job directory was absent after the response was copied.

## Failure and authority boundaries

- Remote execution requires both the existing OmniVoice enable switch and the
  separate Mac-remote enable switch.
- The caller admits one remote decode at a time with a non-blocking lock.
- Text is carried in JSON over SSH stdin and is not interpolated into the SSH
  command.
- Worker output paths and cleanup IDs are structurally validated.
- Lock, timeout, SSH, manifest, inference, or copy failures return a candidate
  error to the existing canary router.
- The checked-in policy remains 10%, owner-allowlisted, and Qwen3 remains its
  control and candidate-error fallback.

## Environment repairs made during validation

- Mac OmniVoice venv: added `scipy` and `tokenizers` required by the checked-in
  bundle synthesizer.
- Local Qwen3 CPU venv: added `accelerate` required by its `device_map=cpu`
  load path.

These are isolated virtual-environment changes; no system Python or production
service configuration was modified.

## Merge-readiness review

The branch was refreshed against GitLab master at
`1fdcde8bffd8336fcda408f364a949c95b8e1ffc`: it was three commits ahead and
zero commits behind, so no baseline merge or history rewrite was required.

The broadened TTS/voice suite passed 271 tests. Two additional tests failed
identically on an isolated worktree at the unmodified master commit: one binds
to a Linux-only installed-binary path, and one expects exactly three fixtures
although master contains a fourth fixture. They are recorded as pre-existing
baseline failures rather than branch regressions.

Python 3.9 and 3.12 compilation passed. Ruff passed for the new dispatcher and
its tests. Review added conservative validation for the SSH destination and
remote SCP path, including rejection of option-style hosts, shell metacharacters,
and parent-directory traversal. The hardened path completed another live
cross-node decode at RTF 2.52 with verified hashes and remote cleanup.

The checked-in GitLab pipeline builds and tests the Rust workspace only; it does
not collect the Python TTS tests. Consequently, a green GitLab pipeline is a
repository regression signal but is not evidence for this adapter by itself.
The Python compilation, Ruff, 271-test suite, canary success, fault injection,
and live cross-node checks above remain the merge evidence for this change.

GitLab did not create an MR pipeline after two branch updates, so the required
CI commands were also run manually on Linux. `cargo build --workspace
--all-targets` passed. `cargo test --workspace --no-fail-fast` completed with two
pre-existing failures: the Codex-essential extras test expects 67 tools while
master currently exposes 69, and the S626 spawn-failure test expects
`GrantDeclined` while the observed result is `Supervisor(Busy)`. This MR has no
diff under `Cargo.toml`, `Cargo.lock`, `crates/`, `bin/`, or `.gitlab-ci.yml`, so
these Rust failures are recorded as master baseline failures, not TTS adapter
regressions.
