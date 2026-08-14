# Gate 7Z ModelScope Controlled Runtime Result

Date: 2026-08-13

## Verdict

`PASS` for one bounded ModelScope ABot-World Studio execution through the
deployed Agent-Bridge MCP surface. This result does not admit a persistent
runtime.

## Provenance

- Source and deployed binary: `fe172e9ab57b54447f656a6e580336d82fe0dab0`
- Toolset: `codex-modelscope-abot`
- Tool: `modelscope_abot_run_once`
- Provider: `modelscope.studio.amap_cvlab.abot-world-0`
- Run: `abot-live-1786682623267`
- Intent: `gate7z-live-activation-fixed-20260813`

## Observations

- `tools/list` returned 57 tools and included `embodiment_lease` plus
  `modelscope_abot_run_once`; `browser_navigate` was absent.
- The MCP client acquired the process-local `body-mac` write lease before the
  call and released it after the call.
- The tool returned `agent_bridge.modelscope_abot_run_once_receipt.v0` with
  status success. The implementation only returns success after observing a
  positive FPS value, invoking the Studio stop action, and observing zero child
  frames after stop.
- The captured pre-stop frame visibly reports `1.0 FPS` and contains the
  submitted prompt plus a rendered interactive scene.
- Evidence PNG: `evidence/modelscope_abot_gate7z_controlled_runtime_2026_08_13.png`
- Evidence SHA-256:
  `0325afd8e45536b1b2ff29c1c16882bd45a48113972f8fee0d82ead4e9b3e54d`
- Evidence dimensions and size: `800x1075`, `689613` bytes.

## Boundary

The screenshot is captured before the stop action so it can show the live
stream. Lifecycle closure is established by the successful tool result after
the stop action and zero-child-frame check. The run used network and hosted
Studio execution; no local model runtime or persistent provider session was
admitted.
