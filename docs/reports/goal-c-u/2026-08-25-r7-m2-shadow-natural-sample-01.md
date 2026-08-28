# R7 M2 shadow natural sample 01

Date: 2026-08-25 (America/Los_Angeles)

Status: historical observation retained, but superseded as durable threshold
evidence by the 2026-08-27 continuity audit. The original report bytes and
state root are not available in the current ledger, so this sample does not
count toward owner-review readiness. M2 runtime remains unadmitted.

> Continuity correction (2026-08-27): this report accurately records the
> invocation-local three-report review observed at the time. It did not bind
> that review to a retained state-root identity or an independent report
> anchor. The current macOS production directory metadata proves the two later
> reports were never written there, and no retained copy was found on aio2.
> Treat the result below as historical task evidence, not current durable-ledger
> evidence. See `2026-08-27-r7-shadow-evidence-continuity-audit.md`.

## Why this is natural evidence

An independent execution stream advanced and deployed Agent-Bridge while this
worktree was idle. On continuation, the local branch was at `a94c73b5`, remote
`master` was at `d364e3b9`, and the installed binary was built from
`925cf3fe`. The current task therefore had a real continuity gap: review the
concurrent change, preserve it, and restore this worktree to the current
master without overwriting either source or production state.

The worktree was advanced with a verified `ff-only` alignment to
`d364e3b9`. This observed recovery is the candidate. It is not the owner's
foreground message, a synthetic fixture, or a retrospective relabeling of the
morning disk-pressure event. The latter was deliberately rejected as a fresh
candidate because more than the frozen six-hour recovery horizon had elapsed.

The privacy-minimal candidate persisted only hashes:

- trigger kind: `recovery`;
- signal SHA-256:
  `30c905307f1a9f639af9c85e45bc078e3165af8ad8c0dcd9f764bbc54293b198`;
- verified evidence SHA-256:
  `c507b54b29a4c5aa90631284f1a0191bfb3532b898416c1935fa84b594e19151`;
- observed/evaluated time: `1787708687177` ms,
  `2026-08-25T18:44:47-07:00`;
- foreground state: `active`; and
- candidate-local UTC offset: `-420` minutes.

The hashed evidence bound only content-free alignment facts: local and remote
commit equality, the installed feature commit, and `ff-only` recovery. No raw
conversation, prompt, repository diff, owner content, or arbitrary note
entered the private report.

## Preview correction and decision

The first preview exposed a caller-side timestamp construction error:
`date +%s%3N` on this host produced a 19-digit value rather than the required
13-digit Unix milliseconds. That preview was state-free and was discarded.
The corrected call explicitly took the first 13 digits of `%s%N`; its complete
before/after Resident snapshot was identical.

The corrected preview and recorded decision both returned:

```text
report_id=shadow-0e020472e6f378f3cb451e72dcdba2ea
would_wake=false
suppression_reasons=[foreground_session_active]
projected_provider_calls=0
actual_provider_calls=0
actual_wakes_created=0
m2_admitted=false
```

This is useful negative evidence: an already-active owner session made a
separate cognition wake unnecessary. It closes the required natural
suppression observation without arguing for M2 admission.

## Private-state acceptance

Recording added exactly one report. Every pre-existing Resident file retained
the same content hash, mode, owner, group, size, mtime, and ctime; the wake
ledger remained byte-identical with one wake. The new 1,692-byte report is mode
0600 with one link and SHA-256
`60f19d03bd75bcfaea9fe47a5accd689a98741f4b0c6e544235747ede3815c45`.
Exact replay returned `already_recorded` and preserved that hash.

A concurrent report,
`shadow-b424faeb28dee44da69089ac45b91034`, appeared in the same interval. It
has valid safe boundaries, but no durable natural/mechanics provenance and may
represent the same underlying recovery observation. The complete-ledger
review therefore classified it conservatively as mechanics evidence rather
than guessing or double-counting it as natural.

## Complete-ledger review

The invocation-local classification covered all three reports:

- natural: `shadow-0e020472e6f378f3cb451e72dcdba2ea`;
- mechanics: `shadow-8f03704a03546fa9f76f7f969aa7a3ba`;
- mechanics: `shadow-b424faeb28dee44da69089ac45b91034`.

The review itself left the complete private state byte- and metadata-identical
and returned:

```text
status=collecting
report_count=3
natural_report_count=1
mechanics_report_count=2
unclassified_report_count=0
natural_trigger_counts={recovery: 1}
natural_would_wake_count=0
natural_suppressed_count=1
natural_suppression_reason_counts={foreground_session_active: 1}
actual_provider_calls=0
actual_wakes_created=0
owner_stop_label_active=false
ready_for_owner_review=false
m2_admitted=false
```

At invocation time this sample removed only the
`missing_natural_suppression` blocker. It no longer removes that blocker from
the current durable ledger. The current ledger has four blockers:

- fewer than three natural reports;
- fewer than two natural trigger kinds; and
- no natural `would_wake=true` report; and
- no retained natural suppression report.

## Next gate

First deploy the report-anchor hardening and anchor the surviving legacy
mechanics report through exact idempotent replay. Then continue ordinary work
and record only genuinely observed candidates in that same anchored state
root. No historical receipt is reconstructed, and no candidate discovery,
timer, scheduler, background loop, provider call, or real M2 wake is admitted.
