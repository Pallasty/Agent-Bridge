# BioCortex Retrieval Runtime Boundary Proof

Date: 2026-06-11

## Purpose

This proof closes part of the gap between technical attestation and a future
runtime approval packet. It verifies that the BioCortex retrieval shadow surface
is still opt-in, read-only, fail-open to baseline behavior, and unable to
authorize default retrieval influence.

The proof does not approve runtime influence and does not change
`memory_search`.

## Proof Command

Run:

```bash
AB_BIOCORTEX_RS=/Data/CascadeProjects/biocortex-rs \
scripts/prove-biocortex-retrieval-runtime-boundary.sh
```

The script writes a local proof bundle containing:

- `default-disabled.json`: feature-built CLI surface without
  `AB_BIOCORTEX_RETRIEVAL_SHADOW=1`; expected `status=runtime_disabled`.
- `kill-switch.json`: enable and disable envs both set; expected
  `status=operator_disabled`.
- `enabled-sample.json`: opt-in shadow run; expected `status=ok`,
  `read_only=true`, `runtime_adapter_approved=false`, and
  `default_search_order_changed=false`.
- `latency-samples.jsonl`: repeated enabled shadow runs.
- `proof-summary.json`: machine-readable summary with p95 latency and boundary
  assertions.

The summary schema is:

```json
{
  "schema": "agent_bridge.biocortex_retrieval.runtime_boundary_proof.v0",
  "read_only": true,
  "writes_approval": false,
  "runtime_adapter_approved": false,
  "default_search_order_changed": false
}
```

## Runtime Claims

The proof must establish:

- default runtime state is disabled unless
  `AB_BIOCORTEX_RETRIEVAL_SHADOW=1` is set;
- `AB_BIOCORTEX_RETRIEVAL_DISABLE=1` wins over enable;
- enabled shadow mode uses explicit query/candidate rows only;
- side-signal coverage is at least 0.8 for the canonical boundary fixture;
- p95 side-signal latency is recorded for the target host;
- every result keeps `runtime_adapter_approved=false`;
- every result keeps `default_search_order_changed=false`.

## Future Ordering Call Sites

The proof also records the only known default retrieval call sites a future
ordering-influence design would need to review:

- `crates/store/src/sqlite.rs:3067`:
  `SqliteStore::memory_search` for FTS ranking.
- `crates/store/src/sqlite.rs:3228`:
  `SqliteStore::memory_search_hybrid` for FTS plus graph RRF.
- `crates/store/src/sqlite.rs:5585`:
  `SqliteStore::memory_search_semantic` for vector ranking.

Current BioCortex shadow work must leave those functions unmodified. Any future
default influence must name the exact modified call site, prove fail-open
behavior, measure default-path latency, and obtain separate human
authorization.

## Approval Boundary

This proof can satisfy evidence fields for default-disabled behavior,
kill-switch behavior, opt-in shadow behavior, and p95 side-signal latency. It
does not satisfy human authorization and does not make the approval packet ready
for default retrieval influence.
