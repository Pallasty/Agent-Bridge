# Temporal Truth And Retrieval Telemetry Audit Result

Date: 2026-07-10

Status: `REVIEW_REQUIRED / CAUSALITY_BLOCKED / AMBIENT_WAIT / NO_WRITE`

## Decision

Do not merge the parallel automatic supersede-retirement patch, run outcome
reinforcement/decay, or open ambient stage 2 from this result.

The frozen structural audit found explicit stale-active lifecycle conflicts,
but it does not know whether a whole memory row and a claim inside that row have
the same lifecycle. The repair must therefore resolve claim-versus-row
semantics before it retires anything.

The retrieval telemetry cannot distinguish eval traffic from organic traffic.
All current reinforce/decay candidate interpretation remains causally blocked.
The next telemetry slice is an additive producer label contract followed by an
organic-only shadow; it is not an apply pass.

Ambient stage 2 remains `WAIT` because only one of three maturation conditions
passes.

## Frozen Source

Protocol commit:

```text
d4fcf7363832fe6ecdccca3b5cc01a2328e4d6b4
```

Execution hardening commit (same signals and gates; one explicit SQLite read
snapshot plus `as_of` upper bounds):

```text
9302c5043b2226a7bd767e29f95228f8f80ce98b
```

Parent:

```text
c83ac016dc5d2844ad47d64dbe9d59aa259add6d
```

Both helpers ran from the tracked bytes at the execution hardening commit with
the same `as_of=1783732107`. A pre-hardening diagnostic run is inadmissible and
excluded from every result below; its cross-query counts moved while external
writers remained live, which is why the single-snapshot hardening was required.

Private aggregate packets stayed under ignored `data/`, untracked, and mode
`0600`:

| Packet | Bytes | SHA-256 |
|---|---:|---|
| temporal | 1,522 | `4648fba4dfb20aa443d81308c6dbef9b3068d9b6c7af75ff0922f63ebd3a72d9` |
| telemetry | 3,709 | `6d33bfb69d0d2119abe48310f9f5feefe3b967abd017359da529d2c5cd264646` |

Neither packet contains a memory key, query, content, session id, or database
path. Both connections report one consistent read snapshot, `mode=ro`,
`query_only=true`, and `total_changes=0` before and after the audit.

## Temporal Result

Verdict: `REVIEW_REQUIRED`

Population:

| Metric | Count |
|---|---:|
| memory rows | 1,450 |
| active memory rows | 1,074 |
| lifecycle edges inspected | 103 |
| unique actionable candidate rows | 30 |

Signals:

| Structural signal | Count | Interpretation |
|---|---:|---|
| active row with non-empty `superseded_by` | 3 | direct lifecycle/status conflict |
| active target of `supersedes` edge | 3 | direct edge/status conflict; may overlap the preceding rows |
| active declared supersedes target | 14 | declaration says historical, target still active |
| declaration source missing matching edge | 13 | source-row count, not a 13/14 target ratio |
| bounded `must_block` state older than 14 days | 2 | review currentness before reuse |
| post-supersede/invalidate access rows | 2 | exposure after signal; causality not asserted |
| active corrected target | 11 | informational; correction co-surface is expected |
| correction source missing `corrects` edge | 0 | correction edge coverage is complete for this snapshot |
| active target of `invalidates` edge | 0 | no signal |
| active duplicate dedupe key | 0 | no signal |
| aging constraint review | 0 | no signal |
| malformed tags | 0 | no signal |

Private candidate-manifest digest:

```text
19535fdc8b018fc46bfef488dcd63c39ca987a98dbbb15a00f067aa5dd0c2b45
```

This result is directionally consistent with the known-prior manual M2 finding
in forum #119 post #3072, but it is not an independent semantic replication.
It neither reads the frozen truth anchors nor adjudicates memory prose.

### Temporal Decision

The evidence supports a lifecycle repair lane, but not the current whole-row
auto-retirement implementation as-is. Before a write patch can advance, a
synthetic contract must distinguish:

1. a row that contains exactly one superseded claim;
2. a row containing both superseded and still-current claims;
3. missing and self-referential targets;
4. an explicit row-level retirement declaration;
5. idempotent edge creation plus reversible status transition.

Until that contract exists, `continuity_supersedes:*` remains an audit signal,
not automatic authority to archive the target row.

## Retrieval Causality Result

Verdict: `BLOCKED_NEEDS_TRAFFIC_CLASS`

The current `retrieval_surfacing` schema has no `traffic_class` column. The
audit did not inspect query text or infer source from key prefixes, modes,
timing, or sessions.

Three-day search slice, excluding bootstrap:

| Metric | Value |
|---|---:|
| exposures | 1,924 |
| used stamps | 173 |
| aggregate use rate | 8.99% |
| rows with observable traffic class | 0 |

By search mode:

| Mode | Exposures | Used | Use rate |
|---|---:|---:|---:|
| fts | 480 | 46 | 9.58% |
| hybrid | 589 | 32 | 5.43% |
| semantic | 855 | 95 | 11.11% |

By rank band:

| Band | Exposures | Used | Use rate |
|---|---:|---:|---:|
| r00-05 | 1,242 | 135 | 10.87% |
| r06-15 | 682 | 38 | 5.57% |
| r16-30 | 0 | 0 | 0.00% |
| r31+ | 0 | 0 | 0.00% |

Mature, unconsumed, active-memory behavior slice:

| Metric | Count |
|---|---:|
| surfacing rows | 3,981 |
| distinct active memories | 514 |
| current-rule reinforce candidates | 42 |
| current-rule decay candidates | 300 |
| rows with valid traffic class | 0 |

Because origin is unobservable, the number of eval-contaminated candidate
memories is bounded only as:

```text
reinforce: 0..42
decay:     0..300
```

Zero is not an estimate. It is only the logical lower bound when no labels
exist. The upper bounds mean every current candidate could include eval
traffic. The private candidate-manifest digest is:

```text
f76249ccc34c421be3a6983d1ca60b59f0d72a27082830fdbe0add64599568bd
```

### Retrieval Decision

Keep `retrieval_outcome_apply` blocked. A separate implementation protocol may
add `traffic_class=organic|eval` at the producer boundary, leave historical
rows explicitly unknown, and run a labelled organic-only shadow. It must not
backfill labels from query text or reinterpret mode as traffic origin.

## Ambient Result

Verdict: `WAIT`

| Condition | Observed | Gate | Pass |
|---|---:|---:|---|
| total bootstrap stamps | 89 | 100 | no |
| distinct used-at days | 5 | 7 | no |
| clean stamps | 56 | 50 | yes |

Recheck after at least two additional distinct used-at days. If all conditions
open, the next admissible experiment remains reinforce-only shadow with no
decay and no apply authority.

## Parallel And Portfolio Read

- ArrowQuant m24 still has no closeout post after its exclusive claim in
  forum #115 post #3067; no new ArrowQuant job was started.
- The separate untracked Temporal Truth Projection design and uncommitted
  `supersede-enforcement` worktrees were not changed.
- The already-landed multiplicative `memory_reinforce_active` implementation
  at `fd3650cfd` means the later durable note describing that fix as pending is
  itself stale planning context. No duplicate reinforce implementation should
  be started.
- BioCortex, SpecFormer, MemoryArena runner, successor rerun, release, version,
  and tag lanes remain closed or gated exactly as before.

## Verification

Passed locally without remote CI:

```text
bash scripts/verify-memory-evidence-audits.sh
python3 -m py_compile (both helpers; external pycache)
bash -n scripts/verify-memory-evidence-audits.sh
git diff --check
```

The synthetic verifier covers labelled, unlabeled, partially labelled,
malformed-schema, lifecycle-conflict, no-write, and identifier-leak cases.

## Boundary

This report authorizes no store mutation, schema migration, correction,
archive, supersede, importance change, ranking change, environment change,
daemon restart, deploy, benchmark claim, CI run, release, version, or tag.
