# Interoception implementation continuity — 2026-09-15

## Result

The original request to retain the audit in AB memory/board and implement
Interoception v1 already has implementation and historical live evidence.
Resume from that evidence, not from the August 26 v0 audit.

Memory anchors:

- `agent_bridge_interoception_v1_audit_and_implementation_decision_20260827`
- `agent_bridge_interoception_v1_implemented_20260827`
- `agent_bridge_interoception_v1_live_gate_pass_20260827`

Board: thread **137**, original decision **3409**; implementation **3410**;
controlled live acceptance **3411**; process-tree, runtime custody, terminal
rusage and delegated cgroup follow-ups **3412–3415**. These are historical
claims, not fresh deployment attestations.

## Current source and runtime checks

Recovery checkout was `codex/repair-quality-gates-20260903` at `ff80bf94`.
The worktree was clean at recovery. Relevant retained source includes:

| Original requirement | Current evidence | Remaining limit |
| --- | --- | --- |
| Truthful coverage and body identity | `body_telemetry.rs`, Linux v1 projection | Whole-host health must not be inferred from required-channel coverage |
| Sampling interval and TTL | Linux collector reuses the latest sample within the minimum interval and emits age/expiry | On-demand; no continuous sampler |
| Swap, critical mounts and PSI | Linux `BodySample` and pressure inputs | GPU utilization and disk/network throughput remain unavailable |
| Thermal, power and network status | Linux projection reads existing OS sources | Additional projections are not all part of the canonical observation payload |
| Separate collector/task accounting | Explicit collector scope, process-tree binding, terminal rusage and workload receipt types | Each scope retains its own completeness conditions |
| Span lifecycle | Active/terminal caps, unique binding, terminal observer and TTL paths | Later durable receipt deployment is a separate R9 lane |
| Canonical afferent seam | `body_observation.rs` and `embodiment_projection.rs` call world aggregation and shadow attention | Resident wake integration remains a later value-dependent step |

The current connected MCP returned `agent_bridge.body_status.v1`,
`enabled=false`, `status=disabled`, `mode=shadow_only`. This verifies that the
installed surface knows v1 and that this connection is not sampling. It does
not attest every installed implementation detail or validate enabled sampling.

## Working plan

Recovery found one retained adapter defect: it preserved the sample capture
timestamp but also put elapsed cache age into `ObservationEnvelope.freshness_ms`.
World-core adds that field to elapsed time at consumption, so a 600 ms sample
could be rejected against a 1000 ms TTL as though it were 1200 ms old.
The adapter now retains the capture timestamp and adds zero extra age. A
regression checks acceptance at 600 ms and exactly 1000 ms, then rejection at
1001 ms even when the upstream freshness label still says fresh.
This is a local source repair; deployment is not part of this continuation.

Validation on the recovery checkout:

- Baseline telemetry: 29 tests passed.
- Repaired afferent adapter: 4 tests passed, including the new TTL boundary case.
- Embodiment projection integration: 10 tests passed.
- `rustfmt --check --edition 2021 crates/bridge/src/body_observation.rs` passed.
- `git diff --check` passed. Existing unrelated compiler warnings remain.

Closeout validation after integrating onto `origin/master` at `c8e64722`:
`cargo check -p ab-bridge --all-targets` passed; telemetry, afferent adapter,
and embodiment projection tests passed (30, 4, and 10 respectively).
The touched Rust file passed `rustfmt --check`; the worktree was clean and
`git diff --check` passed. Runtime deployment remains out of scope.

1. Retain the original audit and implemented design; link this recovery note.
2. Verify the retained telemetry and afferent tests on the current checkout.
3. Reconcile thread 137 with the September decision board and keep an ordinary
   agent-reported plan for navigation; test success is not independent product
   acceptance.
4. Collect value only through genuine work using admitted explicit surfaces.
   The original target is ten natural tasks, at least five paired spans, zero
   false-fresh or safety violations, and an owner usefulness assessment.

The September 3 decision board in `docs/ACTIVE-PRODUCT-ROADMAP.md` governs R9:
it is frozen for expansion/deployment, with retained-defect repair and read-only
incident/cost review allowed. Earlier board posts describing publication,
provisioning or deployment as the next step are historical sequencing only.
This continuation adds no new natural-task evidence and does not claim that
the value gate has passed.
