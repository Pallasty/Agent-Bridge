# Projection Provider Gate 8C: ModelScope Attempt Preview Result

Date: 2026-08-15

## Result

Gate 8C was implemented in `98e6ecd8f07537ab424d9d0ce467ab80c9623e00`
and deployed with the reconciled master build
`0224e9870861b850db821a086970c306445b6956`.

`modelscope_abot_attempt_preview` now derives the exact production task id and
request digest before execution authority or a body-write lease is supplied.
It reports existing-task disposition, Gate 8B recovery state, and typed local
admission blockers without persisting the prompt or task.

## Verification

- `cargo test -p ab-bridge modelscope_abot --lib --quiet`: 15 passed.
- `cargo check -p ab-bridge --all-targets`: passed.
- `python3 -m pytest -q tests/test_modelscope_abot_*.py`: 108 passed.
- Reconciled `app-control` and `system-control` tests: 27 passed.
- Installed binary: `v0.14.0-1624-g0224e987`.

An independent installed-binary stdio check with runtime opt-in reported:

- `modelscope_abot_attempt_preview` exposed and raw `browser_navigate` absent;
- 59 tools in the bounded profile;
- a new request with no blockers and `ready_for_authorized_call=true`;
- `preview_grants_authority=false`;
- no task record written and no task-directory change;
- no browser or external provider execution.

## Boundary

The result proves deterministic, read-only admission preview. It does not prove
that ModelScope is healthy, grant owner authority, acquire a body-write lease,
or admit automatic retry. Existing MCP sessions must reconnect before the new
tool is available through their live process.
