# Engram G1.4 WASI G2L — execution, host, and runtime result

This receipt follows the owner's authorization to merge `1ec12679` and to
execute, host, and integrate the structurally accepted G2L component.

## Landed source

`1ec12679` was fast-forwarded into `master` and pushed to both configured
remotes. The runtime follow-up is implemented in the same isolated master
worktree and remains default-off:

- feature: `g14-wasi-component-runtime`;
- module: `crates/bridge/src/g14_component_runtime.rs`;
- operator command: `g14-wasi-component`;
- dependencies: `wasmtime 46.0.1`, `wasmtime-wasi 46.0.1`;
- no MCP tool is registered and no open component/plugin registry is created.

The command requires both `--artifact` and an expected lowercase `--sha256`.
It rejects a digest mismatch before parsing or instantiating the component.
The WASI host registers only preview-2 clocks/io interfaces. It does not
inherit stdio, preopen directories, environment variables, networking, or
other host capabilities.

## Execution evidence

Artifact:

`g14-clock-probe.component-3.wasm`

SHA-256:

`0b20cc46741a5a9a99a75f67c4c56bf1632b7f398162aa5b8eadd15c08c7642b`

The direct Wasmtime CLI and the Agent-Bridge runtime command both returned:

```json
{"wall-epoch-seconds":946684800,"logical-nanoseconds":0,"quantum-nanoseconds":1000000}
```

The first Agent-Bridge attempt exposed a host-threading defect: synchronous
Wasmtime WASI p2 setup cannot be called inside the already-running Tokio
runtime. The command was moved before Tokio construction; the rerun passed.
This is now an explicit runtime invariant in `main.rs`, not a hidden workaround.

The negative path was also exercised: passing `--sha256 deadbeef` exited 1
with a digest-mismatch error and did not execute the component.

## Verification

- `cargo check -p ab-bridge --no-default-features --offline --locked`: PASS;
- `cargo check -p ab-bridge --features g14-wasi-component-runtime --offline --locked`: PASS;
- focused runtime unit tests: 2 passed;
- Agent-Bridge feature-gated CLI execution: PASS;
- SHA mismatch fail-closed path: PASS;
- default feature set remains free of Wasmtime runtime activation.

## Authority boundary

This proves one explicit, hash-pinned structural G2L component can execute
under a narrowly configured Agent-Bridge host. It does not authorize arbitrary
third-party components, dynamic discovery, MCP exposure, production artifact
installation, or deployment. Those remain separate decisions.

Status:

**G2L EXECUTION PASS — HOST ADAPTER PASS — DEFAULT-OFF RUNTIME INTEGRATION PASS**

