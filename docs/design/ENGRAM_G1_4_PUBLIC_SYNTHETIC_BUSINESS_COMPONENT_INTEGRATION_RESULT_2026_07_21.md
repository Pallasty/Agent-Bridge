# Engram G1.4 public-synthetic business component construction and host integration

Date: 2026-07-21
Verdict: `PASS_CONSTRUCTION_HOST_INTEGRATION__EXPLICIT_CLI_ONLY`

## 1. Delivered

- pinned public WIT fixture and guest Rust component source;
- locked guest dependency graph using `wit-bindgen 0.58.0`;
- `wasm32-wasip2` release component construction with Rust/Cargo 1.96.0;
- host-side typed `evaluate` invocation through the existing default-off
  `g14-wasi-component-runtime` feature;
- explicit artifact SHA-256 verification;
- host input bounds enforcement; and
- release integration script with correct-SHA and bad-SHA paths.

The guest has no WIT imports. The host adds the existing WASI linker only for
the shared runtime seam; the business component itself receives no ambient
capability.

## 2. Evidence

Executed:

```text
scripts/check-engram-g14-public-synthetic-business-component-integration.sh
```

Result:

- guest release build: PASS, `--offline --locked`;
- host release build: PASS, `--offline --locked`,
  `--no-default-features --features g14-wasi-component-runtime`;
- host → component → typed report: PASS;
- expected report: `revision=7`, `entity-count=12`,
  `occupied-cells=9`, `transition-count=4`,
  `occupancy-per-mille=750`, `report-code=WORLD_STATE_V0`;
- wrong artifact SHA: rejected with `component SHA-256 mismatch`;
- out-of-bounds host input: rejected before invocation; and
- MCP/daemon-http source surfaces: no integration leak.

## 3. Pinned identities

| Identity | SHA-256 / version |
| --- | --- |
| guest component artifact | `f83e4b5f20e4fea218de64c2f91b931777becb691d202609cbf21d5e5cc018f1` |
| guest source `src/lib.rs` | `a2415f7158085511fb15acc8279b98cd789f5bf0527500dd824ebbb1d060d828` |
| guest `Cargo.toml` | `1ba14f2d2c7b8253f1c4c87da60df7bd17dcac40d691bf33c330acb85c165f2c` |
| guest `Cargo.lock` | `e83f270d3972ac874094b15bbd2eac732e37432af379f3fda61f04d95981abb9` |
| host runtime source | `c54fcd6ed0bf495b8e73ab4accffc3631f5a420e65e8b39a39e1b20ca62ff015` |
| CLI source | `d29f0166ef824ada2ae279acd1ec24218fba2416897dda1cb2d4caff33803fb6` |
| integration script | `b8a64332d58c5c38333e1090c05bad26c7811cf037289374d0e445f322660291` |
| toolchain | `rustc/cargo 1.96.0` |
| Wasmtime host | `46.0.1` |

The `.wasm` is intentionally not committed as a production binary. The
source, lockfile, WIT, and integration script are the reproducible inputs;
the artifact hash above is the observed build receipt.

## 4. Authority boundary

This result adds one explicit operator CLI probe. It does not add an MCP tool,
default-profile surface, dynamic registry, arbitrary upload, remote execution,
production write, private-data path, or native sandbox/clock-isolation claim.

Release deployment remains a separate gate. The current production binary was
not replaced by this branch.
