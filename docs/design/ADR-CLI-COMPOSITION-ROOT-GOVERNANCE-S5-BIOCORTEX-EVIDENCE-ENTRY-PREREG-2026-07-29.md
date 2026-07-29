# ADR: Preregister BioCortex evidence-entry CLI extraction

- Status: Accepted
- Date: 2026-07-29
- Decision scope: `crates/bridge/src/main.rs`
- Coordination: Agent-Bridge forum thread #254
- Base revision: `1b6ba3df40131a75d53a2a9406c2af14a2e7690d`
- Implementation status: preregistered only

## Context

The first four composition-root slices established three useful extraction
shapes:

- S1 moved a complete narrow nested family;
- S3 moved flat execution adapters while retaining root schema and dispatch;
- S4 moved a complete medium-width nested family.

After S4, `main.rs` contains 20,443 lines and 106 top-level `run_*`
functions. The lower-risk candidates from the S0 inventory are complete. The
remaining listed families are BioCortex, avatar, and dream.

BioCortex is the best next domain to assess because it matches Agent-Bridge's
foundation-first Agent Cognitive Substrate Extension role and its established
shadow/review-before-authority boundary. It is not safe to move as one family,
however. `BioCortexOp` has 28 nested operations and its implementation spans
roughly 3,500 lines. The family currently combines:

- a local external-process shadow digest;
- static capability-ledger file consumption;
- replay comparison that can open `state.db` and write a caller-selected
  fixture;
- feature-gated retrieval shadow evaluation;
- opt-in audit, planning, execution, and review packets;
- temporary SQLite store trials and controlled-order fixtures;
- batch diagnostics and redacted evidence aggregation;
- runtime-readiness, transition, authorization, and downstream handoff
  decision surfaces.

Those operations share a BioCortex-specific JSON-to-text formatter,
`shadow_json_display`, with 382 call sites. They do not share one authority or
side-effect boundary. Moving all 28 commands at once would combine external
process execution, store access, filesystem writes, compile gates, and
runtime-transition claims in one review.

## Decision

Preregister one later S5-A implementation slice that creates a binary-private
`cli::biocortex` module and moves only:

1. `run_biocortex_shadow_digest`;
2. `run_biocortex_capability_ledger_report_packet`;
3. `shadow_json_display`.

`shadow_json_display` is BioCortex-private despite its generic name: every
accepted-base call site belongs to a BioCortex executor. During the staged
extraction, the remaining root-owned BioCortex executors may import this helper
from `cli::biocortex`. That temporary mixed ownership is explicit and must not
be generalized into a crate-wide presentation utility.

The implementation must keep in `main.rs`:

- the complete 28-variant `BioCortexOp` clap schema;
- both selected early-dispatch arms;
- the post-Hub `Cmd::BioCortex { .. }` exhaustiveness entry;
- `run_biocortex_replay_compare` and every retrieval approval, opt-in, store
  trial, fixture, diagnostics, evidence, runtime-transition, handoff, and
  feature-gated shadow executor;
- all BioCortex schema constants, controlled-order and redacted-evidence
  structs, loaders, and fixture helpers;
- store construction, runtime policy, feature gates, and authority decisions.

No public library API is created. The module is an organizational boundary
inside the binary crate.

## Why These Two Adapters

`run_biocortex_shadow_digest` delegates to the existing read-only shadow
adapter and renders its result. It may execute the local BioCortex example,
but it does not link BioCortex into Agent-Bridge, mutate Agent-Bridge memory,
or change retrieval order.

`run_biocortex_capability_ledger_report_packet` reads one caller-selected
ledger file, consumes it through existing library logic, and renders a static
report packet. It does not execute BioCortex, open `state.db`, write memory,
register a tool, or grant runtime authority.

They are adjacent, small, and do not require the store or feature-gated
retrieval imports used by later BioCortex operations. Their combined boundary
is narrower than ReplayCompare and every opt-in/store/runtime-transition
operation.

## Preserved Contracts

The later implementation must preserve:

- root `biocortex` spelling and all 28 nested command names;
- every flag, default, required/optional rule, help paragraph, and parse
  failure for the two selected operations;
- execution before shared Hub construction;
- shadow checkout resolution, benchmark selection, timeout, raw-output, and
  supported-benchmark reporting;
- capability-ledger read/parse behavior and v3/v5 report-packet rendering;
- JSON schemas, field values, pretty-text headings and line order;
- stdout/stderr, error context, and exit status;
- all boundary fields stating no Agent-Bridge runtime link, memory mutation,
  retrieval-vector change, executor enablement, or runtime authority;
- default tool profiles, MCP manifests, store schemas, retrieval ordering,
  feature gates, runtime policy, and authority.

The extraction must not strengthen a shadow result into a cognition,
retrieval-quality, runtime-readiness, or authority claim.

## TDD and Baseline Gate

Before production movement, capture from the accepted implementation base:

1. `agent-bridge --help`;
2. `agent-bridge biocortex --help`;
3. help for `shadow-digest`;
4. help for `capability-ledger-report-packet`;
5. `shadow-digest --json` and text output against an explicitly missing
   checkout, so the failure/degraded contract is deterministic;
6. capability-ledger JSON and text output for the checked-in v3 and v5
   fixtures;
7. missing-ledger stderr and exit status.

The first implementation edit must add a focused ownership test that fails
while the two executors and formatter remain defined in `main.rs`. Production
movement is allowed only after that RED is observed.

Acceptance requires:

- byte-for-byte equality for all four help surfaces;
- byte-for-byte equality for deterministic stdout/stderr fixtures and exact
  exit-code equality;
- existing capability-ledger consumer, display-packet, and review-artifact
  tests;
- a source-boundary test proving ReplayCompare, retrieval/store/runtime
  executors, schema constants, and `SqliteStore` remain outside
  `cli::biocortex`;
- focused module tests for the moved formatter;
- scoped `rustfmt`, `git diff --check`, and
  `cargo check --locked --offline -p ab-bridge --all-targets --quiet`.

If external shadow output contains an accepted-base nondeterministic duration
or temporary path, the baseline packet must name and normalize only that
field. Boundary, status, benchmark, example, verdict, demonstrated keys,
failed predicates, and limitations must remain compared.

## Stop Conditions

Stop and return to design if:

- either selected adapter needs `SqliteStore`, `StateStore`, Hub, MCP, memory
  writes, retrieval-order mutation, or runtime-transition policy;
- moving the formatter requires a generic public presentation API or
  duplication;
- clap schema or dispatch ownership must move;
- Cargo features, library exports, tool profiles, or manifests must change;
- output, exit, error, or external-process behavior drifts;
- another owner begins overlapping `main.rs` work without coordination.

## Explicit Non-Goals

S5-A does not authorize:

- `run_biocortex_replay_compare`;
- retrieval shadow or opt-in behavior changes;
- store trial, controlled-order fixture, diagnostics, evidence aggregation,
  runtime-readiness, transition, authorization, or handoff extraction;
- BioCortex runtime linking, retrieval influence, default search-order
  changes, memory/graph writes, policy changes, deployment, or reconnect;
- avatar, dream, Instinct, `mcp_tools.rs`, library API, or Cargo work.

## Rejected Alternatives

### Move the complete BioCortex family

Rejected for S5 because 28 operations cross multiple authority and effect
boundaries. The review would be too broad to prove behavior preservation.

### Include ReplayCompare

Rejected because ReplayCompare can open `state.db`, collect a live fixture,
write a caller-selected fixture path, and execute the external adapter. It
needs a separate effect-aware gate.

### Move all schema and routing before executors

Rejected for S5-A after independent review. Moving the 28-variant schema and
roughly 750-line routing match would remove a large mechanical region, but the
new child module would then call 28 executor implementations still owned by
the crate root. Rust permits descendant access to private ancestor items, yet
that would create 28 temporary dependency edges from `cli::biocortex` back
into the composition root. It would also require default and feature-gated
baseline coverage for every nested help surface before effect-coherent
executor ownership has been established. S5-A prefers a narrow forward
ownership step over a large inverted adapter seam.

### Move every read-only-looking opt-in packet

Rejected because their contracts form an ordered authorization and
runtime-transition evidence ladder. Physical movement should follow a
separate cumulative boundary audit rather than name-based grouping.

### Select avatar or dream instead

Deferred. Avatar remains broad and process/UI/platform-effect sensitive.
Dream remains broad with extensive shared store and report helpers. Neither is
a safer immediate slice than the two low-authority BioCortex entry adapters.

## Rollback

Revert only the later S5-A implementation commit, restoring the two executor
definitions and formatter to `main.rs`. Keep this ADR as the audit record. Do
not preserve a failed extraction by adding compatibility aliases, duplicating
the formatter, or widening visibility beyond the binary crate.
