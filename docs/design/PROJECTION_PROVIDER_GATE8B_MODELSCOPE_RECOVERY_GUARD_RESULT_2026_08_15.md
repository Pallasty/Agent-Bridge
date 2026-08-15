# Projection Provider Gate 8B: ModelScope Recovery Guard Result

Date: 2026-08-15

## Result

Gate 8B is implemented and deployed from `master@7f21126076b0f6c90735faa9234d2e984a026fc5`.

The bounded recovery guard now:

- exposes `modelscope_abot_provider_status` as a read-only MCP tool;
- derives provider recovery state from at most 256 durable Gate 8A task records;
- applies a 5, 15, 30, then 60 minute cooldown after consecutive provider failures;
- resets the failure streak after a completed task;
- treats a prior-process `running` record as an interrupted provider attempt;
- blocks new external execution before opening the browser or writing a new task record;
- performs no network probe, automatic retry, or persistent runtime admission.

## Verification

- `cargo test -p ab-bridge modelscope_abot --lib --quiet`: 13 passed.
- `cargo check -p ab-bridge --all-targets`: passed.
- `python3 -m pytest -q tests/test_modelscope_abot_*.py`: 108 passed.
- Full library baseline comparison retained three pre-existing upstream failures; each reproduced unchanged at `github/master@6e603b4c`.
- Release deployment completed from `github/master@7f211260` and the installed binary reports `v0.14.0-1614-g7f211260`.

An independent stdio process using `AGENT_BRIDGE_TOOLSET=codex-modelscope-abot` reported:

- 58 tools;
- `modelscope_abot_provider_status` exposed;
- raw `browser_navigate` absent;
- 5 task records considered, 0 invalid, 0 omitted;
- 2 consecutive provider failures and no prior success;
- the 15 minute cooldown already elapsed;
- runtime opt-in absent in that verification shell, so execution remained ineligible;
- `network_probe_performed=false`, `external_execution_started=false`, and
  `persistent_runtime_admitted=false`.

The result proves local recovery-state projection and fail-closed admission. It does not claim ModelScope provider recovery or a successful positive-FPS ABot run.

## Activation

Existing MCP sessions retain the previous process image. Reconnect each session before using `modelscope_abot_provider_status` through the live MCP surface.
