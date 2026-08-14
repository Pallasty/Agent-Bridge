# Gate 8A ModelScope Task Protocol Result

Date: 2026-08-14

## Verdict

- `PASS` for the durable task protocol, default-closed authority boundary,
  failure persistence, cleanup, and restart-safe read-only status projection.
- `BLOCKED_PROVIDER` for a new successful receipt and completed-task
  idempotent replay. ModelScope Studio accepted the start action but did not
  report positive FPS during either a 20-second or 60-second observation
  window.

This result does not admit a persistent runtime, automatic retry, or a
background executor.

## Provenance

- Source, GitLab master, and GitHub master:
  `9b32e2f3d21f38ef5be5fad1b862e62955451f34`
- Deployed binary: `agent-bridge 0.14.0
  (v0.14.0-1607-g9b32e2f3; 9b32e2f3d21f)`
- Toolset: `codex-modelscope-abot`
- Provider: `modelscope.studio.amap_cvlab.abot-world-0`
- Installed MCP surface: 57 tools, including `embodiment_lease`,
  `modelscope_abot_run_once`, and `modelscope_abot_task_status`; raw
  `browser_navigate` remained absent.

## Validation

- Playwright read-only diagnosis showed that the Studio shell can take about
  25-30 seconds to expose its prompt and action controls. The adapter now
  polls the prompt for at most 45 seconds and the start control for at most 20
  seconds instead of relying on a fixed 12-second sleep.
- `cargo test -p ab-bridge modelscope_abot --lib --quiet`: 9 passed.
- `cargo check -p ab-bridge --all-targets`: passed.
- Provider Python regression suite: 108 passed before integration.
- The full `ab-bridge` library run had 1800 passes, 3 ignored tests, and 3
  failures that reproduced unchanged on the pre-Gate-8A upstream baseline.
- Release deployment rechecked that the remote ref had not moved, preserved
  all deployed capability markers, and verified runtime asset parity.

## Live Failure Evidence

The final bounded call used request id `gate8a-live-20260814-long1` and a
60-second FPS observation window. It acquired and released the process-local
`body-mac` lease, reached the Studio start path, then returned:

`Studio stream did not report positive FPS before deadline;
cleanup_stop_observed=true; close_observed=true`

Its durable task is `abot-task-0816080022abcefc60d27eda` with status `failed`,
failure class `provider_timeout`, retry policy
`new_request_id_required_after_failure_or_interruption`, and
`persistent_runtime_admitted=false`. The task directory is mode `0700` and
the record is mode `0600`. A fresh MCP process read the same record through
`modelscope_abot_task_status` with `read_only=true`,
`status_projection_mutated_record=false`, and no receipt included.

Earlier DOM-readiness failures were also persisted with distinct request ids;
none were retried under the same id. Every live attempt observed stop/close
cleanup and released its lease.

## Remaining Gate

A future provider-available window must produce one successful receipt, then
repeat the exact same request id and digest to prove the returned `run_id` is
unchanged, `idempotent_replay=true`, and
`external_execution_repeated=false`. Until then, the historical Gate 7Z
positive-FPS receipt remains the latest successful provider execution, while
Gate 8A is admitted only for its durable protocol and failure behavior.
