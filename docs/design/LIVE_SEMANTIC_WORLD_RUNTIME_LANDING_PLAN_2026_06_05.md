# Live Semantic World Runtime - Landing Plan

**2026-06-05 - role: direction guard + acceptance planning**

Parent documents:
- [Live Semantic World Runtime v0](LIVE_SEMANTIC_WORLD_RUNTIME_V0_2026_06_04.md)
- [Phase 0 Spec](LIVE_SEMANTIC_WORLD_RUNTIME_PHASE0_SPEC_2026_06_04.md)
- [Phase 0 Step B Spec](LIVE_SEMANTIC_WORLD_RUNTIME_PHASE0_STEP_B_SPEC_2026_06_05.md)
- [Phase 0 Step C Spec](LIVE_SEMANTIC_WORLD_RUNTIME_PHASE0_STEP_C_SPEC_2026_06_05.md)

Forum anchor: Agent-Bridge design thread #102.

## 0. Purpose

This document prevents the Live Semantic World Runtime lane from drifting into
"build another tool surface" or "build a 3D engine" after the successful onsen
proofs.

The accepted product thesis remains:

> A live world where humans and AI agents interact through different expression
> forms while mutating and perceiving one unified semantic state.

The current work should land in that direction, not merely accumulate adapters.

## 1. Current Verified State

As of this planning pass:

- onsen Step A and Step B are accepted:
  - `cd1061b` - phase-0 Step-A semantic probe.
  - `bddae5b` - pixel-grounded visibility probe.
  - `10d58ee` - live semantic world host.
- Step B proved the load-bearing v0 claim: an out-of-process caller can patch a
  running onsen session and read structured perception from the human-visible live
  root viewport, with `verified=false` on inert or unavailable render paths.
- The onsen proof branch is clean and pushed:
  - worktree: `/Users/pallasting/Projects/onsen-hd-live-semantic-phase0`
  - branch: `codex/live-semantic-phase0-t1`
  - head: `10d58ee`
- Agent-Bridge Step C has been dispatched and claimed by another implementation
  session:
  - worktree: `/Users/pallasting/Projects/agent-bridge-lswr-step-c`
  - branch: `codex/lswr-step-c-world-tools`
  - active WIP in `crates/bridge/*`
- This thread should remain a direction guard and acceptance-planning lane unless
  explicitly reassigned to implementation.

## 2. Layer Boundaries

Keep the runtime landing split into five layers.

| Layer | Responsibility | Current Status | Next Landing Rule |
|---|---|---|---|
| Runtime core | Shared semantic world state, patch log, event stream, branch/rollback, authority, verification semantics | Not built | Do not extract from one seed alone; wait for onsen plus at least one non-spatial seed pressure |
| World adapters | Concrete engines/worlds that map semantic patch/query to live state and render | onsen adapter proven in dev/probe form | Keep each adapter thin, honest, and render-grounded |
| Agent-Bridge MCP surface | Agent-facing tools that call a world adapter | Step C in progress | Stay Tier::Niche, client-only, no fake-green, no product-center drift |
| Expression/present layer | Human-facing and agent-facing presentation of verified results | Not wired in Step C | Step D only; consume present-compatible shape, do not auto-emit yet |
| Verified learning stream | #94-style verified outcomes into memory/training substrate | Deferred | Only ingest claims that passed render-grounded verification |

The Agent-Bridge tools are a bridge into the runtime. They are not the runtime.

## 3. Acceptance Posture

Every landing step must preserve these invariants:

- **Same-render grounding:** visual/perception claims are derived from the render
  surface a human could actually see, not a proxy model dictionary.
- **No green-but-inert:** a logical patch that does not change the human-visible
  render is `verified=false` or `not_verified`.
- **Structured perception first:** screenshots can audit or calibrate, but the
  agent's primary perception is structured world/render data.
- **Patch is never an empty ACK:** patch responses carry before/after visibility,
  applied status, reasons, and verification state.
- **Layer honesty:** a later layer cannot upgrade a lower layer's
  `verified=false` into success.
- **Human-visible costs are explicit:** live-viewport flicker, side effects, save
  isolation, debug-only controls, and viewport mutations are reported.

Use only three top-level verdict families:

| Verdict | Meaning |
|---|---|
| `verified` | The claim was checked against the relevant live semantic/render evidence |
| `not_verified` | The system could not verify, or the evidence contradicted the claim |
| `blocked` | The runtime could not safely attempt the operation |

Avoid verdicts that imply success without evidence.

## 4. Step C Landing Plan

Step C is valuable only if it stays narrow:

- implement `world_query`, `world_patch`, and `world_visibility_query` as
  Agent-Bridge MCP tools;
- make Agent-Bridge a TCP client of the onsen live host;
- keep the tools Tier::Niche;
- return structured not-verified JSON for host-down, timeout, malformed response,
  and host-side `verified=false`;
- add present-compatible provenance fields without auto-calling `present()`;
- do not modify the onsen host;
- do not wire #94, nexus, remote/cross-node world hosts, or branch/rollback.

Direction-guard acceptance should check these before H-gate:

1. `world_visibility_query.entities` is required, per C0 sign-off.
2. `world_query` may retain the smoke default `["bath"]`.
3. `world_patch` defaults `visibility_entities` to `[entity]`.
4. Endpoint env naming is consistent with the accepted C0 contract. The forum
   claim mentions `ONSEN_LSWR_HOST_PORT`; the Step C spec mentions
   `ONSEN_LSWR_PORT`. The implementation should make this explicit and avoid a
   silent mismatch.
5. `verified_to = "onsen_live_root_viewport"` appears only when the host result
   is verified.
6. Host failures are machine-readable not-verified results, not opaque panics and
   not tool-level success with missing evidence.

H-gate remains:

- H1 MCP vs direct-host parity.
- H2 boundary honesty, including host-down and alpha-zero.
- H3 Tier::Niche profile gating.
- H4 present-compatible provenance.
- H5 no Agent-Bridge regression.

This thread can prepare or run H-gate only after the Step C owner posts DONE or
the owner explicitly asks for intervention.

## 5. Phase 0 Closure Criteria

Phase 0 is closed only when all three are true:

1. **Onsen proof artifact exists and is recoverable.**
   The onsen branch containing Step A/B remains pushed, clean, and referenced in
   the design docs.
2. **Agent-facing access works.**
   An agent can call the three MCP tools and receive the same honest result the
   direct onsen host would have returned.
3. **A direction decision is recorded.**
   The project explicitly chooses whether the next step is:
   - Step D: present/#94 integration over the accepted Step C surface;
   - Phase 1: extract runtime-core schema and event/branch model;
   - Nexus seed: add a temporal/causal adapter before extracting schema;
   - pause: keep the proof as validated research.

Do not treat a green `cargo test` alone as Phase 0 closure. The closure is a
human/AI interaction proof, not only a Rust tool build.

## 6. Recommended Next Sequence

### Step C: finish the bridge

Let the current Step C owner finish implementation in the isolated worktree.
This thread should review and gate after DONE, with special attention to the env
name mismatch and the required `entities` schema.

### Step D: wire expression, not learning first

After Step C passes, add a design-only Step D spec for `present()` integration:

- map verified world results into the #92 output/expression lane;
- preserve `verified_to` and `verify.method`;
- show `not_verified` honestly to the human;
- do not write to the #94 verified-outcome stream until the present boundary is
  accepted.

The order matters: expression must be trustworthy before it becomes training
data.

### Phase 1: extract runtime core only after two pressures

Do not extract a generic `world-core` from onsen alone. Add the nexus seed or an
equivalent non-spatial/causal world pressure first, then extract:

- semantic entity/component shape;
- patch and expected-effect schema;
- event stream and causal links;
- branch/rollback;
- authority and participant model;
- verification ledger.

Rust becomes the natural home for this core once the schema is pressured by more
than one adapter. Before that, Rust should stay in Agent-Bridge client/adaptor
code rather than pretending to be the runtime.

## 7. Human/AI Interaction Shape

The target interaction is not "AI uses an editor." It is:

```text
AI proposes or applies semantic patch
  -> world adapter mutates live state
  -> human-visible render changes
  -> runtime emits structured perception + interaction feedback
  -> AI revises, explains, branches, rolls back, or presents
```

Humans may be players, collaborators, reviewers, directors, or influence sources.
They do not need to manipulate design controls for the system to learn from their
interaction. The key is that every human-visible result and human interaction can
be anchored back to the shared semantic world model.

AI agents may be creators, editors, observers, critics, simulators, or
negotiators. Multiple AIs can interact through the same world, but the runtime
must make authority, provenance, and rollback explicit before multi-agent editing
becomes default.

## 8. Drift Triggers

Pause and re-evaluate if any of these happen:

- Step C broadens from three Tier::Niche tools into default Agent-Bridge surface.
- The tools return successful-looking results when the onsen host is unavailable.
- `present()` or #94 ingestion is wired before H-gate accepts Step C.
- The system starts treating screenshots as the agent's primary perception.
- The runtime core is extracted before a second seed pressures the schema.
- Branch/rollback is discussed as a UI feature without an event/causal ledger.
- Debug-only live viewport mutation leaks toward player/shipping builds.

## 9. Owner Decisions Needed Later

No decision is required to continue waiting for Step C DONE. The next owner-level
decision arrives after H-gate:

- merge or archive the onsen proof branch;
- accept or reject the Agent-Bridge `world.*` surface;
- choose Step D expression wiring versus nexus second-seed pressure;
- decide whether Rust runtime-core extraction should start.

Until then, the best use of this thread is acceptance readiness, drift detection,
and planning.
