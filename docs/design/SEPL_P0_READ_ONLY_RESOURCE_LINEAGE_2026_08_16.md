# SEPL P0 Read-Only Resource Lineage

Status: source-only implementation candidate

Authority packet: forum thread `#380`, post `#6164`

Baseline: `60ea96cda559b2bd2db433493326f7c26501e345`

## Scope

P0 adds an additive SQLite `resource_versions` table and a bounded
`StateStore::resource_lineage_read` projection. The only admitted resource kind
is `agent_md`, matching the first concrete consumer selected by the L7/SEPL
roadmap.

P0 does not provide a write, commit, rollback, MCP, CLI, scheduler, or runtime
policy surface. Opening a writable `SqliteStore` creates the empty table as an
additive migration; after that, the P0 API only reads and validates existing
rows. `schema_meta.version` remains unchanged because the existing v43/v44
feature-dependent ladder is authoritative and this substrate is an independent
additive rung.

## Integrity Contract

Each row binds:

- resource id and kind;
- monotonic version;
- claimed resource-content SHA-256;
- optional predecessor version and predecessor-record SHA-256;
- observation time;
- a domain-separated, length-framed SHA-256 over those fields.

The read projection sorts deterministically and reports violations for malformed
hashes, duplicate/invalid versions, record-hash drift, incomplete predecessor
bindings, and predecessor version/hash mismatch. A bounded suffix is reported as
`verified_bounded_suffix`, never as a complete verified lineage.

The record hash proves only that the stored lineage metadata is internally
consistent. P0 does not read the referenced resource content, so every report
sets `content_readback_verified=false`.

## Safety Floor

- `mutation_supported=false` is fixed in the report.
- There is no `StateStore` mutation method for `resource_versions`.
- Existing AGENT.md drift remains propose-only and is not called or modified.
- `present_outcomes` and `outcomes_memory_drift` are not read or written.
- No resource, retrieval, ranking, routing, memory, browser, provider, or task
  state behavior changes.

## Future P1 Gate

Any future resource commit or rollback must have fresh owner authority and must
read the resource back after the write, recompute its content SHA-256, and prove
equality with the selected lineage entry. The P0 metadata hash cannot substitute
for that readback falsifier.

## Acceptance Evidence

- complete lineage validates independent of input row order;
- content or predecessor hash drift is rejected;
- a truncated suffix cannot masquerade as complete;
- fresh SQLite open creates the additive table and returns an honest empty
  report;
- scoped tests, all-target store check, and `git diff --check` pass.
