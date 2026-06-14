# BioCortex Integration Assessment

Date: 2026-06-10

## Decision

Integrate `biocortex-rs` into Agent-Bridge, but do not replace the current
`ab-seed-bridge` with it yet.

The first Agent-Bridge integration should be a read-only shadow bridge that
runs deterministic BioCortex reports and exposes the result as status, MCP, or
dashboard telemetry. A direct swap into `EmbeddingBackend` is not appropriate
until a separate adapter proves that BioCortex can preserve AB retrieval
contracts and add measurable value.

Follow-up implementation decision: keep Seed source code as a legacy sidecar,
but remove it from the default Agent-Bridge runtime dependency graph.
Agent-Bridge now compiles Seed-facing CLI/MCP surfaces through a disabled
compatibility shim. The historical `crates/seed-bridge` crate remains in-tree
for replay/reference work, but it is excluded from the default workspace and
uses the remote AiOT `seed_neuron` package when built directly.

## Landed Status

The first BioCortex integration is now an external shadow digest, not a linked
runtime dependency:

- `crates/bridge/src/biocortex_shadow.rs` resolves a local `biocortex-rs`
  checkout from `--checkout`, `AB_BIOCORTEX_RS`, sibling checkout paths, or
  `/tmp/biocortex-rs-ab-eval`;
- it runs sanctioned examples with `cargo run --offline --quiet --example ...`;
- it parses deterministic `key=value` output into
  `agent_bridge.biocortex_shadow_digest.v0`;
- it exposes explicit boundary flags showing that AB did not link BioCortex,
  mutate AB memory, alter retrieval vectors, or expose reward/structure
  mutation APIs;
- CLI surface: `agent-bridge biocortex shadow-digest`;
- MCP surface: `biocortex_shadow_digest` under the Standard profile.

Phase 1.1 adds a replay comparison harness:

- CLI surface: `agent-bridge biocortex replay-compare`;
- MCP surface: `biocortex_replay_compare` under the Standard profile;
- input: the existing AB `ShadowCortexReplayFixture` shape, either collected
  from `state.db` or replayed from a CLI fixture file;
- output schema: `agent_bridge.biocortex_replay_comparison.v0`;
- the harness projects AB events into a stable fixture summary with a SHA-256
  hash, source/scope counts, feature-key counts, event preview, and recommended
  BioCortex benchmark;
- it then runs the selected BioCortex shadow digest side-by-side.

This is deliberately not closed-loop replay yet. Phase 1.1 began as
side-by-side evidence for adapter readiness and source alignment, not a claim
that BioCortex changed AB behavior.

Phase 1.2 defines the first BioCortex fixture-input adapter:

- BioCortex example:
  `/Programs/Users/Pallasting/Documents/CascadeProjects/biocortex-rs/examples/ab_fixture_projection_shadow_adapter.rs`;
- benchmark name: `ab_fixture_projection`;
- input: path to AB `agent_bridge.biocortex_ab_fixture_projection.v0` JSON;
- implementation: std-only narrow parser, preserving BioCortex's zero-dependency
  constraint;
- output: deterministic `key=value` report with
  `ab_fixture_projection_consumed=true` and `adapter_demonstrated=true` when
  schema/hash/source/scope counts are coherent.

Implementation note: `/tmp/biocortex-rs-ab-eval` was a temporary checkout and
was later cleaned from this host. A durable checkout was restored at
`/Programs/Users/Pallasting/Documents/CascadeProjects/biocortex-rs` after DNS
recovered on 2026-06-10, and the adapter was re-applied there.

Phase 1.3 lands the AB-side substrate replay contract inside the same fixture
projection:

- field: `substrate_replay_plan`;
- schema: `agent_bridge.biocortex_substrate_replay_plan.v0`;
- contents: deterministic open-loop event pulses, input neuron mapping,
  fixed synapse/readout plan, pulse hash, expected BioCortex adapter output
  keys, and explicit read-only boundary flags;
- purpose: give BioCortex a narrow substrate-level replay input without
  allowing AB memory writes, reward injection, topology mutation, or retrieval
  vector changes.

After phase 1.3, AB emits the replay plan and the durable BioCortex adapter
consumes it. The adapter builds a local temporary microcircuit, applies pulses
to scope-specific input neurons, keeps plasticity blocked during replay, and
reports substrate replay predicates such as `substrate_replay_consumed`,
`event_pulses_applied`, `input_spikes`, `integration_spikes`, and
`integration_trace_bounded`.

Supported shadow benchmarks:

- `ab_fixture_projection` -> `ab_fixture_projection_shadow_adapter`
- `scaled_morphology` -> `scaled_morphology_shadow_adapter`
- `temporal_credit` -> `temporal_credit_shadow_adapter`
- `minimal_morphology` -> `morphology_shadow_adapter`

The default AB dependency graph remains free of both Seed and BioCortex. This
was checked with `cargo metadata --no-deps` and
`cargo tree -p ab-bridge --no-default-features -e normal`.

## Evidence

The current AB Seed bridge is an embedding wrapper:

- it depends on `seed_neuron` through `../../../AiOT/rust/seed_neuron`;
- it wraps the selected AB embedding backend;
- it returns the inner backend vector unchanged;
- it observes memory events through the substrate in parallel;
- it preserves the L3 `384` dimensional cosine retrieval contract.

`biocortex-rs` has a different shape:

- standalone crate, library name `biocortex`;
- no external Rust dependencies;
- starts from LIF neurons, sparse synapses, STDP, modulation, homeostasis, and
  topology experiments;
- explicitly separates itself from legacy Seed vector-grid design;
- its documented AiOT/Nexus adapter boundary is read-only shadow mode.

Historical validation against temporary checkout of
`git@github.com:pallasting/biocortex-rs.git`:

- HEAD: `1f0184dcb299faf54cb639bc5f4c186a5cb3cb57`
- commit: `feat: add s38 multi-route co-activation independence (column-orthogonality)`
- command: `cargo test --manifest-path /tmp/biocortex-rs-ab-eval/Cargo.toml --lib --quiet`
- result: `541 passed; 0 failed`
- command: `cargo run --offline --quiet --manifest-path /tmp/biocortex-rs-ab-eval/Cargo.toml --example scaled_morphology_shadow_adapter`
- result: emitted `scaled_morphology_demonstrated=true` with
  `open_limitation=outcomes_injected_no_autonomous_self_shaped_morphology`
- command: `cargo run --offline --quiet --manifest-path /tmp/biocortex-rs-ab-eval/Cargo.toml --example temporal_credit_shadow_adapter`
- result: emitted `credit_window_demonstrated=true`,
  `distal_first_hop_credit_demonstrated=true`, `specificity_demonstrated=true`,
  and `at_scale_demonstrated=true`
- command: `cargo run --offline --quiet --manifest-path /tmp/biocortex-rs-ab-eval/Cargo.toml --example morphology_shadow_adapter`
- result: emitted `temporal_boundaries_visible=true`,
  `refresh_rescues_evidence=true`, `retention_gap_detected=true`, and
  `behavior_preserved_all=true`
- command: `cargo run --quiet --example ab_fixture_projection_shadow_adapter -- <projection.json>`
- result: emitted `fixture_input_accepted=true`,
  `ab_fixture_projection_consumed=true`, and `adapter_demonstrated=true` for a
  minimal AB projection fixture
- command: `cargo test --all --quiet` in `/tmp/biocortex-rs-ab-eval`
- result: `541 passed; 0 failed`
- command: `cargo clippy --all-targets -- -D warnings` in
  `/tmp/biocortex-rs-ab-eval`
- result: passed

Durable BioCortex checkout status on 2026-06-10:

- path:
  `/Programs/Users/Pallasting/Documents/CascadeProjects/biocortex-rs`;
- HEAD: `1f0184dcb299faf54cb639bc5f4c186a5cb3cb57`;
- local addition:
  `examples/ab_fixture_projection_shadow_adapter.rs`;
- minimal AB projection replay result: `fixture_input_accepted=true`,
  `ab_fixture_projection_consumed=true`, `substrate_replay_consumed=true`,
  `event_pulses_applied=true`, `integration_spikes=2`,
  `integration_trace_bounded=true`, and `adapter_demonstrated=true`;
- validation: `cargo fmt --all -- --check`, `cargo test --all --quiet`
  (`541 passed; 0 failed`), and `cargo clippy --all-targets -- -D warnings`
  passed in the durable checkout.

## Implication

`biocortex-rs` is likely the better long-term substrate direction, but it is
not a drop-in replacement for AB's current Seed bridge. The old bridge answers
"how do memory embeddings flow through a substrate without changing retrieval?"
BioCortex currently answers "can a deterministic biomimetic cortical circuit
show useful substrate properties under controlled reports?"

Those are adjacent but not interchangeable contracts.

## Embedding Adapter Gate

Decision on 2026-06-10: do not add a BioCortex `EmbeddingBackend` adapter to
the default Agent-Bridge runtime yet.

The current evidence is strong enough for read-only substrate telemetry:

- AB can project shadow-cortex events into stable fixture JSON;
- AB can emit deterministic substrate replay pulses without changing memory or
  retrieval;
- BioCortex can consume those pulses in a temporary microcircuit and report
  bounded replay predicates.

It is not yet evidence that BioCortex can replace or wrap AB's embedding
contract:

- AB retrieval still expects a stable vector shape and cosine-ranking behavior;
- the current BioCortex adapter consumes event pulses, not user/query text;
- substrate replay proves observability, not recall quality or ranking lift;
- no AB benchmark has shown improved recall, latency, or retrieval diagnostics
  from feeding BioCortex output back into `EmbeddingBackend`.

The next embedding-related step should therefore be a separate benchmark design,
not a runtime adapter: replay fixed memory/query corpora, compare baseline
embedding rankings against any BioCortex-derived side signal, and require no
retrieval mutation until the side signal proves measurable value.

## Recommended Landing Path

1. Done: keep `crates/seed-bridge` as legacy/reference code, but keep it out of
   the default AB workspace and runtime dependency graph.
2. Done for phase 1: add a BioCortex shadow module without a Cargo dependency.
3. Done for phase 1: support a local path override through `AB_BIOCORTEX_RS`
   and explicit checkout path.
4. Done for phase 1: implement only a shadow digest first:
   - run a deterministic BioCortex benchmark/report;
   - project it into AB-safe JSON;
   - expose it through CLI/MCP/status surfaces;
   - do not mutate memory retrieval, routing, rewards, topology, or global
     substrate state.
5. Done for phase 1.1: add a replay comparison harness that projects AB
   shadow-cortex events and runs BioCortex shadow reports side-by-side without
   changing retrieval.
6. Done for phase 1.2: add a durable BioCortex example that accepts AB fixture
   projections as input while remaining read-only and std-only.
7. Done for phase 1.3 on AB side: emit a substrate-level replay plan that maps
   projected AB events into deterministic BioCortex input pulses.
8. Done for phase 1.3 on BioCortex side: consume `substrate_replay_plan` in the
   durable fixture adapter and report substrate replay predicates.
9. Done for the current gate: do not add a runtime `EmbeddingBackend` adapter
   yet. The first offline retrieval benchmark ran end to end and failed the
   MRR lift gate, so BioCortex remains shadow-only.

## Current Build Note

The earlier host build blocker is removed for the retrieval gate path:
Linux native transparent avatar Wayland dependencies are now behind the
optional `linux-native-avatar` feature. `ab-bridge --no-default-features`
checks no longer pull `smithay-client-toolkit`, `wayland-client`, or
`xkbcommon`.

Validation on 2026-06-10:

- `cargo tree -p ab-bridge --no-default-features -e normal | rg
  'smithay|wayland|xkbcommon'` returned no matches.
- `CARGO_TARGET_DIR=/tmp/ab-target-retrieval-gate cargo check -p ab-bridge
  --no-default-features --example biocortex_retrieval_gate_eval` passed.
- End-to-end side-signal run produced 175 rows for 35 queries, but failed the
  offline gate with MRR delta +0.0190 against the required +0.03.
- After side-signal scorer improvement, an alpha scan showed `alpha=0.80`
  reaches MRR delta +0.0429 with 0 regressions. This is evidence for an
  alpha-policy review, not approval for runtime retrieval mutation.

## Guardrails

- No application-provided reward injection.
- No structural mutation API exposed through AB MCP tools.
- No hidden background learning loop.
- No replacement of AB's returned embedding vector.
- No claim that BioCortex is driving AB cognition until a closed-loop AB
  benchmark proves behavioral lift.
