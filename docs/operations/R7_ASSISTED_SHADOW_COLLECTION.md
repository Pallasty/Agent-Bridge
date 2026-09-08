# R7 agent-assisted shadow collection

Date: 2026-09-05
Status: retained foreground diagnostic procedure; active M2 sample pursuit on
HOLD after the owner-authorized 2026-09-08 closeout. No runtime policy change.

The current decision board and
[`2026-09-08-validation-collection-closeout.md`](../reports/goal-c-u/2026-09-08-validation-collection-closeout.md)
govern whether a product lane is active. Routine status checks or repeated
suppressed reports must not reopen a campaign to fill the sample threshold.
Existing explicit M0/M1 use remains available.

## Problem and scope

Repeated collection checks found no new reports because the existing evaluator
requires explicit submission. Waiting is not collection. The exact number of
missed qualifying events and owner time cost are unknown; do not invent them.
This small workflow change removes the requirement for the owner to recognize
events and type commands. It does not justify an autonomous collector.

The agent doing an ordinary task checks at these existing work boundaries:

| Boundary | Candidate | Required basis |
| --- | --- | --- |
| Resume interrupted work | recovery | Existing task context and a real interruption requiring recovery |
| Observe task failure | failure | Actual execution result; truthful severity and event time |
| Check an explicit commitment | commitment-due | Previously stated commitment and explicit deadline now due |

A routine new turn, status question, successful command, deliberate fixture,
or desire to reach the sample threshold is not a natural candidate. Do not
scan unrelated sessions or private content to find one. No qualifying event
means no report; do not create placeholder evidence or a second ledger.

## Submission procedure

1. Check the current roadmap, installed CLI help, and useful owner basis in
   the admitted state root. Stop on an invalid basis, stop label, or integrity
   failure. Invoke `~/.local/bin/agent-bridge`, never bypass its state-injecting
   wrapper by invoking `.real` directly. Verify the existing ledger identity
   and anchors at that root. Legacy files found on another node do not
   authorize creation of a replacement ledger or cross-node merging; retain
   them separately and report the identity gap.
2. Verify the event using evidence already available for the current task.
   Preserve the actual observation time and explicit due time. Hash stable,
   minimal signal metadata and exact evidence bytes locally; never pass raw
   prompts, logs, secrets, or evidence content to the shadow command. A hash
   alone is not verification. If verification is unavailable, represent that
   truthfully rather than marking it verified.
3. Set foreground state truthfully: an ongoing owner conversation is active;
   uncertainty is unknown. Never wait for an idle period to relabel an active
   event or backdate evaluation to bypass freshness or quiet hours.
4. Before preview, check the admitted state's existing reports for this same
   underlying event. A suppressed report is still recorded evidence. If one
   exists, reference it or replay the exact original candidate, including its
   evaluated timestamp; do not resubmit it with a fresh time or changed hashes.
   The evaluator does not deduplicate every suppressed report for the operator.
   Only a distinct new event may produce another report. For a new event,
   preview with `resident shadow` and the documented typed arguments. Inspect
   suppression reasons and require zero actual provider calls and wakes.
5. For a genuine in-scope event, invoke the same candidate with `--record`.
   Pass `--evaluated-at-unix-ms` with the evaluated timestamp from the preview
   report's candidate; omitting it uses the current time instead of exact
   replay. Suppression is a valid observation, not a reason to omit the event.
   Do not change the candidate to obtain `would_wake=true`. If submission
   fails, preserve the
   error and stop; do not recursively record collector failures as samples.
6. Read back the receipt and run `resident shadow-review` with every existing
   report classified from known provenance. Natural/mechanics labels are
   invocation-local assertions, not persisted or authenticated facts. Unknown
   provenance must remain unclassified, never guessed to obtain readiness.
7. Include the report ID, trigger, decision, and blockers in the ordinary task
   closeout when a report was added. Exact replay is not a new sample. Do not
   claim full event coverage from the presence of valid receipts.

The full argument and frozen policy contract is in
`../design/RESIDENT_XIAOSHU_M2_SHADOW_V0.md`. Do not copy a historical basis ID,
timezone offset, timestamp, or sample classification without verifying it.

## Acceptance and limits

For retained ordinary-task diagnostics, the next genuine qualifying event
can validate the foreground workflow: the working agent
records it without an owner command reminder, its report passes readback and
integrity review, and actual provider calls and wakes remain zero. The review
may still report `collecting` and `ready_for_owner_review=false`; one valid
event does not satisfy the whole natural-sample threshold. Source documentation
or fixtures cannot establish that this behavioral acceptance has occurred.

This procedure only runs when an agent is working with these instructions.
No running agent means no discovery or recording. Other checkouts or clients
that have not loaded these instructions are not covered. It installs no hook,
timer, scheduler, service, or automatic candidate source; M2 stays unadmitted.

The 2026-09-08 source review established that an `active` owner foreground
session is always suppressed. This subpath therefore cannot itself supply
the natural `would_wake=true` required by the full M2 gate. The CLI also
accepts truthful `inactive` candidates; this does not prove that an admitted
natural workflow has produced one. Active pursuit of the full gate is on
HOLD, rather than repeatedly collecting active-session samples as if that
could close every missing criterion.

Reconsider the active goal only when an already-admitted real task independently
produces a new recovery, warning/critical failure, or explicit due commitment
with verifiable owner cost, and an existing entry can submit it promptly while
the owner foreground session is truly inactive. All original freshness,
quiet-hour, basis, identity, and review requirements still apply. Do not add
a scheduler or collector, wait to relabel an active event, fabricate inactivity,
or relax thresholds to produce this trigger. Two increments without use-value
refreeze the lane under the existing roadmap rule.

Rollback removes the instruction links and this procedure. Existing private
reports remain intact; no binary rebuild or MCP reconnect is required.
