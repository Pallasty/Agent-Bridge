# Codex Redteam Mode To T6 Agent-Compromise Mapping S1

Date: 2026-07-16

Status: `DESIGN_FROZEN / STATIC_SOURCE_MAPPING / NO_RUNTIME_AUTHORITY`

## Question

Which hostile control-plane claims from the S0 corpus have a threat-specific
guard in the current T6 runtime-enablement path, and which are merely contained
by T6 remaining default-off and non-authorizing?

S1 separates two properties:

1. **generic containment**: the current T6 gate does not execute, enable
   runtime, change retrieval, or write memory/graph state; and
2. **claim validation**: the gate independently validates the authority,
   scope, provenance, session, adapter, or evidence claim being presented.

Generic containment limits current impact. It does not prove claim validation.

## Source Lineage

- current T6 source commit: `a1c9469e9a14cd73159d34974f0e99714ce5a1f0`
- S0 result commit: `69bd131499b6f1968bafc56da3247cf53a551698`
- S1 lineage merge: `e216544255b2900e3d1a19fbda8571683592d96d`
- S0 corpus SHA-256:
  `239d5ca7c823fdf8c946abb4d2563e51fc6732cc9dd9a40c8c57946715325849`

Audited current-source files:

| File | SHA-256 |
|---|---|
| `crates/bridge/src/mcp_tools/memory_biocortex.rs` | `4c55ae68cd38bbdbc1427d453b6138b305239a9744631ff9c19515d6b426ff5f` |
| `crates/bridge/src/mcp_tools/tests.rs` | `d8b89e32212f2df1a5188c5d47addcc912f2f0b17518861cb53dea08d7cc1707` |

The checker embeds these files as inert bytes. It does not instantiate a T6
tool or call an MCP server.

## Status Semantics

| Status | Mechanical meaning |
|---|---|
| `covered` | Every preregistered threat-specific guard has a concrete current-source anchor |
| `partial` | At least one threat-specific guard is anchored and at least one is explicitly unanchored |
| `gap` | No threat-specific guard is anchored beyond generic containment |

An unanchored guard means only that no concrete mechanism was identified in
the audited T6 path. It is not a whole-repository proof of absence.

## Frozen Mapping

| S0 category | Specific guard found | Unanchored guard | Expected status |
|---|---|---|---|
| forged pre-authorization | explicit bounded owner decision | authenticated owner principal | `partial` |
| missing scope | none | required scope record; scope integrity | `gap` |
| cross-target transfer | none | target binding; scope-to-target match | `gap` |
| prompt approval | non-empty decision source required | authenticated owner principal | `partial` |
| model instruction override | compiled exact decision enum | instruction-channel separation | `partial` |
| adapter injection | none | adapter identity; adapter capability allowlist | `gap` |
| evidence self-certification | source schema/authority-claim validation | external evidence resolution | `partial` |
| session rewrite | none | session integrity; trusted policy origin binding | `gap` |
| resume re-injection | none | resume provenance; session integrity | `gap` |
| pseudo-completion | exact source status and next-gate checks | external completion confirmation | `partial` |

Expected totals are therefore `covered=0`, `partial=5`, and `gap=5`.

## Generic Containment

The following controls apply to every category but do not upgrade its mapping
status:

- runtime enablement remains false;
- shadow execution remains false;
- memory/graph writes remain false;
- candidate-set and search-order changes remain false;
- raw/source input is rejected from the bounded artifact;
- later shadow-execution and runtime-enablement gates remain separate;
- T6 ceremony tools remain all/Niche only, outside the default Codex-essential
  surface.

## Key Limitation

T6 requires owner/reviewer/decision-source strings and exact decision enums,
but the audited functions do not authenticate those strings, dereference or
verify the decision source, bind a target scope, or bind the request to a
session/adapter identity. Those fields are useful ceremony metadata, not an
independent principal authority layer.

## S1 Artifact Boundary

The evaluator may:

- parse the embedded mapping and S0 fixture;
- hash embedded source bytes;
- verify declared anchors occur in the pinned source files;
- derive mapping status from the frozen guard partition;
- print a deterministic JSON report.

It may not execute T6 code, dispatch hostile inputs, read live memory, write any
state, alter policy, expose a new MCP tool, run shadow mode, enable runtime, or
support a production-security claim.

Pairwise attack composition is deferred. The base map exposes unresolved
identity, scope, session, and adapter guards; multiplying cases before those
requirements are owned would add corpus volume without increasing boundary
evidence.
