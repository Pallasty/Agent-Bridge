# R6 bounded session-finalize maintenance

Date: 2026-08-25 (America/Los_Angeles)

## Admission evidence

This is a Core reliability/continuity increment, not an experiment lane.
Seven-day Tool Atlas telemetry reported:

- 169 `session_finalize` calls and zero tool errors;
- average 522 ms, P95 2,161 ms, and maximum 7,078 ms;
- 41 calls at or above one second and 10 at or above two seconds; and
- clustered slow calls, including repeated calls only minutes apart.

The user cost is synchronous session-end latency. The closure is one Store
change with a copied-production-store replay and ordinary post-deployment MCP
acceptance.

## Root cause and bounded change

On a SQLite backup of the production store, the prior installed binary took
445 ms, 435 ms, and 449 ms for three successive default finalizations. The
same binary took 25-28 ms when decay was skipped or the call was a dry run.
The store had 2,007 active memories and 8,360 non-retrieval semantic edges.

`memory_decay_importance` previously read every active row, read the complete
durable-edge set, and rewrote every active row on every call, even when the
last pass was seconds earlier and the effective factor was approximately one.

The implementation now:

1. defines a per-row due interval as the smaller of six hours and one percent
   of the requested half-life;
2. reads only due rows first and returns without an edge scan or write
   transaction when the due set is empty;
3. leaves `last_decayed_at` unchanged while deferred, so the next due pass
   applies the exact cumulative wall-clock interval; and
4. keeps future anchors eligible so clock-skew repair is not deferred.

For the default 30-day half-life, the maximum scheduling delay is six hours.
No decay is discarded, no background task or schema is added, and archival
can only be delayed within that bound.

## Verification

- Focused decay tests: 4 passed, including the new defer/catch-up/future-anchor
  regression test.
- Store suite: 543 unit tests plus 5 integration tests passed; zero failures.
- `ab-bridge` no-default-features binary build passed.
- Copied-store post-change replay: an intentionally due pass completed once;
  the immediate default follow-up completed in 56 ms. Six already-deferred
  default calls completed in 54-70 ms.
- Source diff check passed. The repository-wide rustfmt check still reports
  unrelated pre-existing formatting drift; the changed hunk follows the
  formatter's proposed shape.

Post-deployment acceptance must verify the installed binary provenance, run
two default finalizations through a fresh MCP child, confirm the second call is
inside the bounded fast path, and retain normal semantic-event readback.

## Post-deployment acceptance

Deployment completed from `master` commit
`c80d47655efcc27907a6e0acac2e1990443d07c0`. The installed real binary reported
that source revision and had SHA-256
`9a90d41051a31e85ac6c716cdb0efea8721c0e972c506d58dc8fffdbc7137eae`.
All three user services executed that same inode/hash with zero restart count
after deployment, and Doctor reported zero failures and zero warnings.

A fresh MCP child performed two ordinary `session_finalize` calls in 127 ms
and 130 ms. Both were admitted and their semantic-event readback remained
present. This validates the bounded fast path against the installed binary.
Only those two acceptance calls were observed in the first post-deployment
hour, so natural-load latency is still insufficient rather than inferred from
synthetic volume. R6 stays in ordinary telemetry with no benchmark-only
follow-up.
