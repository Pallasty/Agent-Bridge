# Outcome Valence Importance Dry Run

Date: 2026-07-02

Scope: `project:/Data/CascadeProjects/agent-bridge`

Status: read-only verification complete; no production apply needed

## Summary

The newly deployed `outcome_valence_importance_apply` tool was exercised in
dry-run mode against the live Agent-Bridge memory store.

Result: the live store already matches the derived outcome-valence importance
targets for every active `present_outcome` row. There is no useful production
`confirm_apply=true` pass to run right now.

No memory rows, graph edges, schema, retrieval settings, runtime flags, or
BioCortex state were changed.

## Runtime And Repo State

Repository:

```text
master == origin/master
HEAD = 5549f47 feat(memory): apply outcome valence to importance
working tree clean
```

Installed binary:

```text
/home/pallasting/.local/bin/agent-bridge.real
size = 69098360 bytes
sha256 = 7445f8a9992d05d65a10349c0598c71426fffd3093152a9ce42d6d137b755258
```

Short-lived MCP `tools/list` with the all profile confirmed:

```text
outcome_valence_importance_apply present = true
```

Doctor after the operator MCP reconnect:

```text
8 ok / 1 warn / 0 fail
```

The warning is stale-client only: seven long-lived MCP child processes under
other Cursor/Claude parents still execute deleted old `.real` binaries. The
installed binary and short-lived tool surface are current.

## Default Dry Run

Invocation shape:

```json
{
  "confirm_apply": false,
  "floor": 0.1,
  "ceiling": 0.9,
  "min_delta": 0.01,
  "max_apply_per_pass": 500
}
```

Tool boundary:

```json
{
  "read_only": true,
  "mode": "valence_importance_dry_run",
  "mutates_ab_memory": false,
  "recomputes_stored_importance": false,
  "changes_memory_search_order": false,
  "writes_valence": false,
  "runs_biocortex": false,
  "supplies_to_biocortex": false
}
```

Summary:

| Metric | Value |
|---|---:|
| `present_outcome_rows` | 3 |
| `derivable_rows` | 3 |
| `candidates` | 0 |
| `applied` | 0 |
| `failed` | 0 |
| `skipped_below_min_delta` | 3 |
| `capped_out` | 0 |

Interpretation: all three active `present_outcome` rows are derivable, but the
target importance value differs from the stored value by less than the default
`min_delta=0.01`.

## Zero-Delta Preview

A second read-only pass with `min_delta=0` was run only to inspect the suppressed
rows. It did not write an audit memory and did not apply changes.

Summary:

| Metric | Value |
|---|---:|
| `present_outcome_rows` | 3 |
| `derivable_rows` | 3 |
| `candidates` | 3 |
| `applied` | 0 |
| `failed` | 0 |
| `skipped_below_min_delta` | 0 |
| `capped_out` | 0 |

Rows:

| Key hash prefix | Old importance | Target importance | Delta | Valence | Rule path |
|---|---:|---:|---:|---:|---|
| `b755ce4b7520` | 0.8 | 0.8 | 0.0 | 0.6 | `verify=rendered_ok+decision=none -> base=+0.6 * conf(browser_eval=1.0) = +0.600` |
| `173c0ec15ace` | 0.8 | 0.8 | 0.0 | 0.6 | `verify=rendered_ok+decision=none -> base=+0.6 * conf(browser_eval=1.0) = +0.600` |
| `3af84defdcb2` | 0.8 | 0.8 | 0.0 | 0.6 | `verify=rendered_ok+decision=none -> base=+0.6 * conf(browser_eval=1.0) = +0.600` |

The hashes are the tool's redacted `key_sha256` prefixes. Raw memory keys were
not emitted by the dry-run result.

## Decision

Do not run `outcome_valence_importance_apply(confirm_apply=true)` on production
state right now.

Reason: the default dry-run has zero candidates. A forced `min_delta=0` apply
would only set three rows from `0.8` to `0.8`, creating an unnecessary rollback
audit record without changing retrieval order.

The feature is therefore deployed and validated, but the production store does
not currently need a retroactive importance repair.

## Next Step

Keep the retro apply tool available for future drift, decay, or backfill
scenarios.

The next useful validation is not an apply pass. It is either:

1. create a few new verified outcome rows in a controlled fixture or copied DB
   and verify default-off future ingest behavior versus
   `AB_OUTCOME_VALENCE_IMPORTANCE=true`; or
2. wait until real future `present_outcome` rows accumulate and run another
   dry-run before considering a confirmed apply.

## Boundary

This pass did not:

- run `confirm_apply=true`;
- write audit memories;
- change stored memory importance;
- change retrieval ranking;
- write graph edges;
- change DB schema;
- enable `AB_OUTCOME_VALENCE_IMPORTANCE`;
- run BioCortex or provide any value to BioCortex;
- change tool profiles, systemd units, daemons, prompts, or runtime flags.
