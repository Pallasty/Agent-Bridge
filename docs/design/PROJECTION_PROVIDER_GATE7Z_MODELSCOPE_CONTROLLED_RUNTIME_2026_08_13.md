# Projection Provider Gate 7Z: ModelScope Controlled One-Shot Runtime

Gate 7Z turns the browser-owned Gate 7Y lifecycle into one bounded Agent-Bridge
MCP operation: `modelscope_abot_run_once`.

The tool reuses the configured `BrowserBackend` and requires all of the
following before execution:

- Browser capability enabled;
- a current process-local embodiment write lease;
- `owner_confirmed: true` on the call;
- `AB_MODELSCOPE_ABOT_RUNTIME_ENABLE=1` at daemon startup;
- the explicit `codex-modelscope-abot` toolset or the all profile.

Each invocation is process-serialized, prompt-hash-bound, limited to a
5–60 second observation window, and closed by a mandatory Studio stop plus
page close. It stores a screenshot and structured receipt under
`~/.cache/agent-bridge/modelscope-abot/`. The receipt distinguishes the admitted
one-shot invocation from a persistent runtime: `one_shot_runtime_admitted=true`
and `persistent_runtime_admitted=false`.

The dedicated `codex-modelscope-abot` toolset exposes the codex-lean base plus
only `embodiment_lease` and `modelscope_abot_run_once`; raw browser controls are
not added to that surface.
