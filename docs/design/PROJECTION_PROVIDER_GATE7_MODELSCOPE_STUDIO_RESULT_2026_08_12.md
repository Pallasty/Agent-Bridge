# Projection Provider Gate 7A: ModelScope Studio Adapter

Date: 2026-08-12

## Result

Agent-Bridge can discover and read the public ModelScope ABot-World Studio from
the current Mac without local CUDA. The Studio was observed as running on an
H20 96 GB instance and its public Gradio readiness endpoint returned `就绪`.

The default-off client is:

```text
scripts/modelscope_abot_provider.py
```

Its default command performs readiness only. `--session-contract` reads the
public Gradio configuration and reports whether a bounded REST lifecycle is
available. It does not accept a generation prompt or register an MCP tool.

## Live contract evidence

The public `/gradio_api/info` advertises start and stop endpoints but omits
their hidden Gradio State parameters. The authoritative `/config` reports:

| endpoint | inputs | outputs |
| --- | ---: | ---: |
| `on_click_start_ws` | 2 (`prompt`, hidden state) | 8 |
| `on_stop_ws` | 3 (two hidden states, `prompt`) | 8 |

Therefore the ordinary named REST API cannot establish a reliably bounded
start/stop lifecycle. A browser/iframe WebSocket adapter is required to retain
the application state and streaming session.

One bounded exploratory start call was accepted after supplying the omitted
initial state. The corresponding stop call could not be confirmed because the
public API did not return the hidden state needed by `on_stop_ws`. No frame or
video artifact was observed, no `SimulatedWorldRollout` was emitted, and the
subsequent readiness check returned `就绪`. This is protocol discovery, not a
successful generation receipt.

## Verification

```text
python3 -m unittest discover -s tests -p 'test_modelscope_abot_provider.py' -v
3 passed

python3 -m py_compile scripts/modelscope_abot_provider.py
git diff --check
```

Live read-only outputs:

```text
ready=true
missing_endpoints=[]
hidden_state_required=true
rest_lifecycle_supported=false
browser_or_websocket_adapter_required=true
runtime_admitted=false
```

## Boundary verdict

`GATE7A_MODELSCOPE_STUDIO_DISCOVERED_READINESS_VERIFIED_SESSION_NOT_ADMITTED`

The next gate is a browser-owned iframe/WebSocket lifecycle probe that must
prove start, bounded observation, stop, and post-stop readiness before any
generated artifact can become a `simulated.generated` rollout receipt.
