# Live Semantic World Runtime - Nexus Seed Pressure

**2026-06-06 - role: P4 second-seed pressure test**

Parent documents:
- [Requirements v1](LIVE_SEMANTIC_WORLD_RUNTIME_REQUIREMENTS_V1_2026_06_06.md)
- [Event and feedback schema](LIVE_SEMANTIC_WORLD_RUNTIME_EVENT_FEEDBACK_SCHEMA_2026_06_06.md)
- [Human input mapping](LIVE_SEMANTIC_WORLD_RUNTIME_HUMAN_INPUT_MAPPING_2026_06_06.md)

Forum anchors:
- `#105` post `#2552`: P4 start notice.

Read-only Nexus source anchors:
- `nexus-civilization/CLAUDE.md`
- `nexus-civilization/server/core/store/event_store.py`
- `nexus-civilization/server/core/store/causal_graph.py`
- `nexus-civilization/server/core/commands/pipeline.py`
- `nexus-civilization/server/core/governance/agent.py`
- `nexus-civilization/tests/test_causal_governance_linkage.py`
- `nexus-civilization/tests/test_seed_substrate_replay.py`
- `nexus-civilization/docs/seed-world-substrate-implementation-plan.md`
- `nexus-civilization/design/adr/adr-0003-seed-world-substrate.md`

## 0. Status

This document is docs-only. It does not modify Nexus, Agent-Bridge runtime code,
Step D present packets, #92 present wiring, or #94 ingestion.

The goal is to pressure the LSWR model with a second seed that is not primarily
spatial or viewport-verifiable.

## 1. Why Nexus Matters

Onsen proved the first concrete LSWR adapter shape:

```text
semantic patch
  -> live spatial/visual state
  -> viewport-visible or not visible
  -> structured visibility evidence
```

Nexus pressures a different shape:

```text
player/AI command
  -> command pipeline accepts or rejects
  -> tick persists world events
  -> event store seals a hash chain
  -> causal graph links causes to consequences
  -> governance may inject naturalized corrective events
  -> replay/snapshot/attention signals provide later evidence
```

That means LSWR core cannot treat `visibility.query` as the universal proof
surface. Visibility is an adapter evidence family. Nexus needs event, causal,
policy, replay, and snapshot evidence.

## 2. Nexus Evidence Surfaces

### 2.1 Command Pipeline

Nexus commands pass through a seven-stage `CommandPipeline`:

```text
format
identity
permission
resource
constitutional
rate_limit
impact
```

For LSWR, this gives a clear `blocked` boundary. A command rejected by the
pipeline is not a failed visual mutation; it is an authoritative policy or
validity block with a stable stage and message.

Required LSWR mapping:

| Nexus result | LSWR verification |
|---|---|
| `PipelineResult.ok=true` | command may proceed to later event verification |
| `PipelineResult.status=rejected` | `blocked` with `reason=command_rejected` and `evidence.stage` |
| `PipelineResult.status=error` | `blocked` or `not_verified`, depending on adapter responsibility |
| impact estimate only | advisory evidence, not verification |

### 2.2 Event Store

Nexus `EventStore` is append-only and hash-chained. Each stored event carries:

- stable `event_id`;
- tick/day;
- source system;
- type/severity;
- affected cities;
- JSON data;
- cause and consequence IDs;
- `prev_hash` and `hash`.

The store exposes `verify_chain()`, Arrow export, range queries, and recent event
queries.

Required LSWR mapping:

| Nexus fact | LSWR core pressure |
|---|---|
| event appended | `runtime.event_persisted` or `runtime.patch_result` evidence |
| hash chain valid | integrity evidence |
| hash chain broken | `not_verified` with `reason=event_hash_chain_invalid` |
| event absent after accepted command | `not_verified` with `reason=expected_event_absent` |
| raw Arrow/SQL export | adapter-specific evidence payload, not core schema |

### 2.3 Causal Graph

Nexus `CausalGraph` stores event nodes and directed cause-to-consequence edges in
RustworkX plus DuckDB. It supports immediate causes, immediate consequences,
full ancestor chains, impact trees, influence scores, and `subgraph_around`.

Required LSWR mapping:

| Nexus fact | LSWR core pressure |
|---|---|
| expected edge exists | causal evidence can verify a claim |
| event exists but edge is missing | `not_verified` with `reason=expected_causal_link_absent` |
| influence score changes | metric evidence, not proof by itself |
| `subgraph_around` returns a neighborhood | presentation/review artifact for causal evidence |

### 2.4 Governance Layer

Nexus governance runs after tick events are persisted. It can observe full world
state, write governance log entries, and inject corrective `WorldEvent` objects.
The player-facing design intentionally naturalizes many interventions as world
events rather than surfacing "the system intervened".

The regression tests make one internal audit rule explicit: governance decisions
can become synthetic `gov::<entry_id>` causal nodes, and injected events carrying
`governance_entry_id` should receive a `governance_decision` edge.

Required LSWR mapping:

| Nexus fact | LSWR core pressure |
|---|---|
| governance decision node exists | internal audit evidence |
| injected event has decision edge | governance causality verified |
| player sees raw governance machinery when design says naturalized | `not_verified` or design `blocked` |
| governance signal changes world without causal audit | `not_verified` |

### 2.5 Seed World Substrate

Nexus already frames Seed as an optional, bypass, non-generative attention layer:

```text
rules engine decides how the world changes
Seed judges which changes are worth attention
LLM advisor explains that attention to the player
```

The accepted boundary is important for LSWR:

- Seed must not mutate `WorldState`;
- Seed must not bypass `CommandPipeline`;
- Seed must not inject governance events;
- Seed output is structured signal, not player-facing prose;
- replay must prove the shadow substrate does not change world state.

Required LSWR mapping:

| Nexus fact | LSWR core pressure |
|---|---|
| attention signal references source events | feedback/attention evidence can be event-anchored |
| replay reports same world state | non-mutating observer verified |
| replay diverges | `not_verified` with `reason=replay_diverged` |
| attention signal has no source events | `not_verified` for causal/world claims |

## 3. Core Objects That Survive Both Seeds

These objects remain good LSWR core candidates:

| Object | Onsen pressure | Nexus pressure |
|---|---|---|
| `World` | spatial scene/session | ticked simulation/session |
| `Entity` | bath, gate, sign, NPC | city, faction, event, governance decision |
| `Participant` | human/AI editor/player | player/AI/NPC/governance source |
| `Patch` or `Command` | spatial mutation | validated player/AI command |
| `Event` | render/input/runtime event | persisted world event |
| `Feedback` | human accept/reject/note | player/advisor/attention signal |
| `Verification` | visibility evidence | event/causal/hash/replay evidence |
| `Branch` or `Timeline` | reversible scene branch | replay/counterfactual event stream |
| `AdapterEvidence` | screen area, viewport | hash chain, causal path, Arrow snapshot |

The shared core is not "3D state". It is a semantic world history with stable
references, participant identity, authority mode, events, feedback, and honest
verification.

## 4. Verification Without A Viewport

Nexus needs LSWR verification methods that do not depend on `screen_area`.

### 4.1 Verified

Use `verified` only when the relevant claim is proven by adapter evidence.

Examples:

```json
{
  "verdict": "verified",
  "method": "nexus_event_causal_verification",
  "verified_to": "event:evt_food_warning",
  "evidence": {
    "event_id": "evt_food_warning",
    "hash_chain_valid": true,
    "expected_causal_edge": {
      "cause_id": "evt_tax_change",
      "consequence_id": "evt_food_warning",
      "edge_type": "direct",
      "present": true
    }
  }
}
```

### 4.2 Not Verified

Use `not_verified` when the runtime made or expected a claim but the adapter
cannot prove it.

Examples:

- command accepted but expected event is absent;
- event exists but expected causal edge is absent;
- governance injected event has no audit link;
- replay produces a different world state;
- attention signal claims importance without source events;
- causal summary is unsupported by the DAG.

### 4.3 Blocked

Use `blocked` when the command cannot or must not proceed.

Examples:

- format invalid;
- actor lacks ownership or authority;
- permission check rejects the action;
- resources are insufficient;
- constitutional kernel rejects the command;
- rate limit rejects the command.

## 5. API Pressure

The current Requirements v1 API list includes `world.visibility.query` because
Onsen was the first concrete seed. Nexus shows the long-term surface should not
make visibility the generic evidence verb.

Candidate direction for P5:

```text
world.get
world.query
world.patch
world.events.query
world.feedback.query
world.evidence.query
world.effect.query
world.causality.query
world.snapshot.compare
world.branch.create
world.branch.compare
world.rollback
world.snapshot.export
```

Seed-specific adapters may still expose sharper verbs:

```text
onsen.visibility.query
nexus.causality.query
nexus.replay.compare
nexus.event_store.query
```

Agent-facing tools can keep small phase-specific names, but the product model
should converge on evidence and effect queries rather than one visual verb.

## 6. Event Schema Pressure

P2's event envelope survives Nexus if `refs` and `provenance` remain flexible.

Needed additions for P5 consideration:

| Field pressure | Reason |
|---|---|
| `refs.events` | Nexus claims often anchor to source/consequence events |
| `refs.causal_edges` | Causal proof is edge-shaped |
| `refs.commands` | Commands and events are distinct |
| `refs.snapshots` | Replay/snapshot comparison needs stable refs |
| `verification.method` | Must distinguish viewport, hash chain, causal, replay |
| `verification.evidence.adapter_kind` | Evidence must be seed-specific |
| `provenance.replay` | Replay source, seed, tick range, and deterministic status |

These should be additive. Do not remove the Onsen viewport references; make them
one evidence family among several.

## 7. Falsifiers

P4 treats the following as design falsifiers:

| ID | Scenario | Expected LSWR result |
|---|---|---|
| `NX-001` | command is accepted but no expected event appears | `not_verified` |
| `NX-002` | event is persisted but hash chain verification fails | `not_verified` |
| `NX-003` | expected cause-to-consequence edge is missing | `not_verified` |
| `NX-004` | governance event lacks internal decision audit edge | `not_verified` |
| `NX-005` | command rejected by pipeline | `blocked` |
| `NX-006` | replay/shadow substrate mutates world state | `not_verified` |
| `NX-007` | attention signal has no source event anchor | `not_verified` for causal claims |
| `NX-008` | player-facing surface leaks hidden governance machinery | `not_verified` or `blocked`, depending on claim scope |

## 8. P5 Recommendation

Do not extract `world-core` from the Onsen-only shape.

The next mainline step should be a core extraction criteria document that
requires every proposed core object or API to pass both seeds:

- Onsen spatial/visual proof;
- Nexus event/causal/governance/replay proof.

Anything that only one seed needs should remain adapter evidence until a third
seed proves it is general.
