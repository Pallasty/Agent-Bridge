# S5ZM: Rust story preflight adapter parity

## Result

The four-stage native migration now composes the typed request, exact source
ingest, accepted voice evidence, scene-bounded chapter selection, render-request
projection, and model-provenance cache keys in one pure Rust function.

For `/story "docs/design/voice-scene/fixtures/story_s1.md" chapter 2`, the Rust
value is exactly equal to the accepted S5ZF Python receipt, including all three
render requests and preflight SHA-256
`6553dcec1ad51e1b6352d0fc7fa2068b38713d1e37dedacbe45b00f3aca4a1bb`.
The from-start projection selects four first-chapter segments. Runtime flags,
evidence drift, unaccepted continuity, unavailable chapters, duplicate voice
mapping, and invalid model provenance fail closed through the composed checks.

## Boundary

Parity is not registration. `story_contract.rs` remains absent from the bridge
module tree and MCP registry. The implementation cannot be reached through a
deployed tool and does not load Qwen, execute ONNX, render/play audio, or write
cache or memory state. Python remains only a frozen test oracle; no interpreter
is embedded or invoked by the Rust path.

## Next gate

Any move to a real `/story` tool now requires a separate owner-authorized Rust
registration review. That review must resolve the current registry-source
provenance drift, define exposure and cancellation/error contracts, then verify
the newly built binary and refreshed client independently. This receipt grants
no such authorization.
