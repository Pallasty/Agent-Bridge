# R7 M2 shadow review v0

Date: 2026-08-25 (America/Los_Angeles)

Status: contract, implementation, automated tests, debug and installed-binary
read-only production-state acceptance, merge, deployment, and service refresh
passed. Evidence remains `collecting`; M2 runtime is not admitted.

## Goal alignment

The product north star remains **persistent subject, intermittent cognition,
reversible bodies**. R7 currently owns a persistent Xiao Shu identity, explicit
bounded M1 cognition, owner evaluation, and a default-off M2 counterfactual
policy. This increment does not add another body or runtime. It closes the
smallest missing evidence seam between private M2 shadow reports and a future
owner decision.

The current foreground conversation was not fabricated into unattended or
natural evidence. The sole installed report remains a technical mechanics
sample. Therefore this increment cannot justify candidate discovery, a timer,
a scheduler, a provider call, or a real wake.

## Delivered review gate

`agent-bridge resident shadow-review` reads the complete private shadow ledger
and accepts repeatable explicit classifications:

- `--natural-report-id` for a genuine manually identified real-task candidate;
- `--mechanics-report-id` for a technical or acceptance-only sample.

Classifications are invocation-local operating assertions. They are not
persisted or cryptographically authenticated. Unknown, duplicate, or
overlapping IDs fail closed, and every report observed in the ledger must be
classified before a ready packet is possible. This prevents selecting only a
favorable subset while keeping the command read-only.

The frozen ready-for-owner-review threshold requires all of:

- at least three natural reports;
- at least two distinct natural trigger kinds;
- at least one natural `would_wake=true` report;
- at least one natural suppressed report;
- exact safe boundaries, valid useful-owner basis bindings, and zero actual
  provider calls and wakes across all reports; and
- no later `distracting` or `harmful` owner label.

Passing this threshold recommends only
`owner_review_of_candidate_source_design_only`. Every packet hard-codes
`m2_admitted=false`. The function acquires no writer lease and has no report
write, provider, wake, scheduler, action, runtime-change, or automatic-memory
call site.

The existing shadow history loader now revalidates each report's exact
serialized owner-evaluation receipt hash, evaluation ID, useful/positive/no-
stop decision, and chronology. A changed basis receipt can no longer influence
either policy history or review aggregation.

## Automated and debug verification

The focused shadow suite passed 11/11 and the complete Resident suite passed
28/28:

```text
cargo test -j 1 -p ab-bridge resident_m2_shadow --no-default-features --lib -- --nocapture
cargo test -j 1 -p ab-bridge resident_ --no-default-features --lib -- --nocapture
```

Coverage includes mechanics classification without writes, a three-report
two-trigger natural ready case that still refuses M2 admission, incomplete and
invalid classifications, later owner stop labels, and corrupted basis receipt
binding. The locked no-default-features CLI build passed and exposed the
documented repeatable flags. Only existing repository warnings remained.

Before merge, the debug binary reviewed the current production ledger with
report `shadow-8f03704a03546fa9f76f7f969aa7a3ba` explicitly classified as
mechanics. A complete before/after snapshot compared every Resident file's
content SHA-256, mode, owner, group, size, mtime, and ctime. All were unchanged;
the file count remained four and the wake count remained one.

The packet returned:

```text
status=collecting
report_count=1
natural_report_count=0
mechanics_report_count=1
unclassified_report_count=0
natural_trigger_kinds=0
natural_would_wake_count=0
natural_suppressed_count=0
actual_provider_calls=0
actual_wakes_created=0
ready_for_owner_review=false
m2_admitted=false
```

Its four blockers are fewer than three natural reports, fewer than two natural
trigger kinds, no natural eligible result, and no natural suppression.

## Deployment and installed acceptance

- Implementation and the frozen design were merged to `master` as
  `c2b8e04719208c54586d4e3686d798da0c856440`.
- The release build completed in 10 minutes 08 seconds. The publisher
  re-fetched `origin/master`, confirmed it remained on the exact build commit,
  and passed the capability-superset gate before replacement.
- Installed version is
  `agent-bridge 0.14.0 (v0.14.0-1864-gc2b8e047; c2b8e0471920)`.
- Installed real-binary SHA-256 is
  `2141e2ac499b4841acbfbbc58cf608afe85b6b7695f5978012dd2cf7733124ca`.
- The prior binary is recoverable at
  `/home/pallasting/.local/bin/agent-bridge.real.bak-deploy-c2b8e04-20260825T095542`;
  matching runtime and audio assets also received publisher-managed backups.
- Daemon, daemon-http, and Palace restarted onto the installed binary's exact
  inode and SHA-256. Both `http://127.0.0.1:7878/healthz` and
  `http://127.0.0.1:7979/healthz` returned `ok`.
- Doctor reported 9 ok, 1 warning, and 0 failures. The sole warning was the
  owner-local `eDP-1` display currently asleep (`dpms=false`,
  `power=false`), not an AB service or deployment defect. No stale AB MCP
  process existed.

The installed command repeated the exact mechanics review. The full private
state snapshot again remained byte- and metadata-identical, with four files
and one wake before and after. The existing 1,692-byte report remained 0600,
single-link, and SHA-256
`9ffc1c95ffba582762200e8835d7e50e6a484acfd0022199cfb2479fb2090a4e`.
The installed decision matched the debug decision exactly: `collecting`, zero
natural evidence, zero provider calls, zero wakes, and M2 unadmitted.

## Resource hygiene

The current isolated worktree's regenerable debug/test target was removed,
freeing 7.0 GiB without touching source or evidence. A later `/Data` increase
was traced to a different, concurrently active worktree's debug/incremental
build and was deliberately left untouched.

## Closure and next gate

This increment closes trustworthy evidence aggregation, not collection or M2
admission. The next goal is intentionally an observation gate: record only
genuine, manually noticed natural candidates during ordinary work, classify
the complete ledger, and wait until the frozen threshold is met. At that point
the owner may review one bounded candidate-source design. Until then there is
no basis for discovery, timers, schedulers, background loops, real provider
calls, or wake execution.
