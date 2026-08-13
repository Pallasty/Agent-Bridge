# ADR: Projection Provider Convergence

**Date:** 2026-08-12  
**Status:** accepted for design; implementation not admitted  
**Parent:** `PROJECTION_STACK_TRUTH_AUDIT_2026_08_12.md`

## Context

Agent-Bridge needs to distinguish three different claims that can all produce
something visually inspectable:

1. a generative model proposes pixels showing a possible future;
2. an engine executes explicit world state and renders the result;
3. a sensor observes the external world.

Treating those outputs as interchangeable would allow generated imagery to be
mistaken for executed or observed truth. Adding one MCP tool per model or engine
would also duplicate transport, replay, provenance, and review behavior already
owned by `present` and LSWR.

## Decision

Introduce a provider-neutral design boundary named
`ProjectionRequestEnvelope`. Do not reuse the existing embodiment
`ProjectionPlan` name or schema.

### Request Envelope

```text
agent_bridge.projection_request.v0

request_id
intent_id
source_world_ref
source_world_revision
projection_class
provider_id
requested_outputs
constraints
authority_ref
created_at
```

`projection_class` is closed in v0:

```text
simulated.generated
simulated.executed
observed.real
```

The request is descriptive. It grants no authority, acquires no lease, invokes
no provider, and does not imply that any output exists.

### Provider Roles

| Role | Example provider | Required output |
| --- | --- | --- |
| `generative_visual` | ABot-World | `SimulatedWorldRollout` |
| `structured_simulation` | Godot, later UE5 | `EngineExecutionReceipt` |
| `real_observation` | browser/device/body adapter | existing observation envelope plus evidence refs |

Provider-specific model, engine, device, and renderer details live under a
namespaced `provider_metadata` object. They do not alter the common verdict or
evidence classes.

### Receipts

#### `SimulatedWorldRollout`

Records a generated visual hypothesis. It must include provider/model identity,
input lineage, generation parameters, artifact hashes, and the fixed evidence
class `simulated.generated`. It must never carry `verified=true` for an external
world effect.

#### `EngineExecutionReceipt`

Records an engine-executed state transition. It must include the before and
after world revisions, action/event ids, structured readback, render evidence,
rollback group, and the fixed evidence class `simulated.executed`. Its verdict
is limited to what the named engine instance executed and re-observed.

#### `ProjectionComparisonReceipt`

Compares two or more immutable receipt refs. It records comparison method,
metrics, mismatches, and reviewer disposition. It cannot promote either input
to a stronger evidence class and cannot rewrite provider receipts.

## Control And Data Flow

```text
semantic intent / world state
        |
        v
ProjectionRequestEnvelope
        |
        +--> generative_visual ------> SimulatedWorldRollout
        |
        +--> structured_simulation --> EngineExecutionReceipt
        |
        +--> real_observation --------> ObservationEnvelope
                                              |
immutable receipt refs -----------------------+
        |
        v
ProjectionComparisonReceipt
        |
        v
world_present / present --> present_replay
```

`present` transports human-facing artifacts. `present_replay` audits that
transport. Neither surface becomes the source of world truth. LSWR remains the
semantic state, action, evidence, and rollback substrate.

## Invariants

1. Evidence class is mandatory and cannot be upgraded by presentation or
   comparison.
2. Every receipt binds to an immutable request id, provider id, source world
   revision, and artifact or structured-state hash.
3. Generated pixels are never evidence that an engine or real device changed.
4. Engine success requires structured post-state readback; a screenshot alone
   is insufficient.
5. Real-world effect claims require a separate observation boundary.
6. Human accept/reject is feedback, not retroactive verification.
7. Rollback is represented in the ledger and verified after application.
8. The request envelope has no execution authority. Any body-affecting action
   still requires the existing embodiment authority and `ProjectionPlan` path.

## First Implementation Gate

The first proof should use an existing Godot host rather than introducing UE5
or ABot dependencies. It must demonstrate one bounded loop:

```text
explicit world state
-> semantic patch/action
-> human-visible render
-> structured post-state and visibility evidence
-> rollback
-> verified restored state and render
```

The proof may reuse Onsen or Nexus, but selection requires a fresh adapter and
test inventory. It must not expose a new MCP tool family; it should map through
the existing LSWR world envelopes and `present` transport.

## Deferred Gates

1. ABot-World provider smoke remains deferred by owner decision.
2. UE5 adapter work requires a real local/remote engine project and a concrete
   need not met by the existing Godot proof host.
3. Runtime registration and deployment require a separate implementation
   review and explicit evidence packet.

## Consequences

- The architecture gains one stable truth boundary instead of model-specific
  MCP surfaces.
- Existing action authority semantics remain unchanged.
- Godot can validate the structured simulation half before model integration.
- ABot-World can later be added as a second provider without being treated as
  an engine or observation source.

## Gate 1 Verdict

`CONTRACT_ACCEPTED_DESIGN_ONLY_RUNTIME_NOT_ADMITTED`
