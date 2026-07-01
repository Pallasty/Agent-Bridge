# Related Keys Materializer Hash Gate

Date: 2026-07-01

Status: implemented, tested, deployed to local `.real`

## Summary

The `memory_related_keys_materialize` writer now emits a deterministic
`selected_edge_hash_v1` for the currently selected edge list and requires
`reviewed_selected_edge_hash_v1` to match before any `dry_run=false` write.

This closes the GHP-1c drift found during the third tiny materialization slice:
a dry-run sample and a live apply call can recompute against a changed graph and
select different edges. The new contract keeps the existing
`apply_confirmation="materialize_related_keys"` gate and adds an edge-plan hash
gate.

## Behavior

Dry-run responses include:

- `selected_edges`
- `selected_edges_count`
- `selected_edge_hash_v1`

Live writes now require:

- `dry_run=false`
- `apply_confirmation="materialize_related_keys"`
- `reviewed_selected_edge_hash_v1=<exact dry-run selected_edge_hash_v1>`

If the reviewed hash is missing or mismatched, the tool returns:

- `blocked=true`
- `linked=0`
- `write_errors=[]`

No graph edge is written before the hash gate passes.

## Canonical Hash

`selected_edge_hash_v1` is a lowercase 64-character SHA-256 hex digest over a
compact JSON projection:

```json
{
  "schema": "agent_bridge.memory_related_keys.selected_edges.v1",
  "edges": [
    {
      "from_key": "...",
      "to_key": "...",
      "edge_type": "relates"
    }
  ]
}
```

The ordered edge sequence is intentionally part of the hash. The hash binds the
exact edge set that will be written; it does not approve PageRank, centrality,
automatic orphan linking, retrieval ranking, or broader candidate expansion.

## Tests

Commands:

```text
cargo test -p ab-bridge memory_related_keys_materialize_write_requires_matching_selected_edge_hash -- --nocapture
cargo test -p ab-bridge memory_related_keys_materialize_dry_run_exact_scope_excludes_parent_scope_candidates -- --nocapture
```

Results:

- `memory_related_keys_materialize_write_requires_matching_selected_edge_hash`: passed
- `memory_related_keys_materialize_dry_run_exact_scope_excludes_parent_scope_candidates`: passed

Supplemental verification in a later session:

```text
cargo test -p ab-bridge --lib memory_related_keys -- --nocapture
cargo test -p ab-bridge memory_related_keys_materialize --no-default-features
```

Result:

- focused `--lib memory_related_keys`: 11 passed, 0 failed
- 5 related tests passed
- 0 failed

The broader target filter covered the materialization plan max-edge cap,
inbound cap, exact-scope dry-run filtering, exact-scope scope requirement, and
the matching-hash live-write gate.

`git diff --check` passed. `cargo fmt --check` was also attempted, but the
repo-wide rustfmt diff path emitted large unrelated formatting diffs in
pre-existing files and then failed with an allocation error. It did not modify
files.

Existing warnings observed:

- `ab-store` mixed-script confusable warning for `coactivation_stats_β_trigger_threshold`
- `ab-bridge` private-interface warning for `ToolPolicy`
- existing unused Option-E helpers

## Boundary

This code change does not expose `memory_related_keys_materialize` in
`codex-essential`. The writer remains outside the compact Codex surface.

## Deployment

Commit:

```text
a936cb1 feat(memory): gate related keys materializer apply hash
```

Deploy command:

```text
scripts/deploy_from_master.sh --yes
```

Deploy result:

- source: `origin/master @ a936cb1`
- deployed binary: `/home/pallasting/.local/bin/agent-bridge.real`
- deployed sha256:
  `f23ce54501d4cf85b824de057bdb3eda79f02e605f7beb2868000936107888f8`
- rollback binary:
  `/home/pallasting/.local/bin/agent-bridge.real.bak-deploy-a936cb1-20260701T132921`
- rollback sha256:
  `c82b6dab1a5ad09f107f87bcd8aaf88248d0c2ed29656803507aad973537fdff`
- deploy feature gate: passed; new binary is a superset of current deployed
  markers

Follow-up deploy after the focused verification record:

- command: `scripts/deploy_from_master.sh --yes`
- source at fetch/build time: `origin/master @ c75bc2a`
- deployed binary: `/home/pallasting/.local/bin/agent-bridge.real`
- deployed sha256:
  `66389e60e2cc648f152aa8fd9d0bc566ea34b2df5ddb6982d42061e472cbb91c`
- previous deployed binary backup:
  `/home/pallasting/.local/bin/agent-bridge.real.bak-deploy-c75bc2a-20260701T133441`
- previous deployed sha256:
  `f23ce54501d4cf85b824de057bdb3eda79f02e605f7beb2868000936107888f8`
- deploy feature gate: passed; new binary is a superset of current deployed
  markers
- installed-binary string smoke found `reviewed_selected_edge_hash_v1`,
  `selected_edge_hash_v1`, and
  `agent_bridge.memory_related_keys.selected_edges.v1`

As of `5b86955`, all commits after `a936cb1` are documentation/report updates:
there is no `crates/`, `Cargo.toml`, or `Cargo.lock` diff from `a936cb1` to
`HEAD`.

Installed-binary smoke used a short-lived all-dev MCP subprocess from the new
`.real`:

- `dry_run=true`, `max_edges=0`: response included
  `selected_edge_hash_v1=dbba465e3f7c8eaee3c8f5be8a9054f6c7f19180e0c8f6d2969a412e395f631d`
- `dry_run=false` with `apply_confirmation` but no reviewed hash:
  `blocked=true`, `linked=0`, `write_errors=[]`

Post-deploy doctor:

- `ok=true`
- `fails=0`
- `warns=1`

The warning is expected until long-lived clients reconnect: 8 MCP server
processes were still executing the old deleted `.real`. Each client needs
`/mcp reconnect` or host-app restart before its eager MCP surface uses the new
hash gate. Short-lived direct `.real mcp` subprocesses already use the deployed
binary.
