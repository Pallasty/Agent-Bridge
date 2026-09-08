# Validation collection closeout — 2026-09-08

Decision: **R4-A FROZEN; active R7 M2 sample pursuit HOLD; R4
HOLD_TRIAL_TOPOLOGY.** The owner requested implementation after the waiting-time
audit. These decisions close the current pursuit of missing samples. They
retain existing useful on-demand capabilities and private evidence.

The audit found no provable hard calendar deadline violation. The reason to
stop active pursuit is missing value evidence or incomplete trial feasibility,
not an invented collection deadline. A reducer's `collecting` result describes
its evidence input, not an indefinitely active product commitment.

## Basis and scope

Source review starts at `065cb69aef81c38610fd8267d829696297d0e943`.
Private-state audit snapshot: **2026-09-08 05:18:29 America/Los_Angeles**.
The follow-up R4 entry inspection completed at **05:43:21** on the same date.
The audit covered known Linux roots and the existing bound Mac roots through
the established SSH connection; it was not a fleet-wide or session-history
scan. No live event was generated, recorded, relabeled, or backfilled.

| Lane | Verified evidence | Disposition and owner-visible consequence |
| --- | --- | --- |
| R4-A | Increment 2 finished 08/24; 18 action rows represent 9 attempts, with 6 completed, 2 cancelled, 1 failed final outcomes. No retained owner daily-use ratings or durable observer-session journal. | `FROZEN`: end active collection and expansion; retain explicitly started foreground use. |
| R7 M2 | Current Mac ledger identity and two report anchors match: one natural failure and one mechanics report, both suppressed, zero actual calls/wakes. Latest natural evaluation was 08/27 18:58:49 PDT, 11.43 days before the audit. | `HOLD` active pursuit of the M2 gate; retain M0/M1 and truthful ordinary-task diagnostics. M2 remains unadmitted. |
| R4 formal | Kickoff already passed, effective 08/31 22:06:18 PDT. Exact formal ledger absent; first event pending; start/end null. Required Avatar/voice receipt source cannot close locally on its Mac writer. | `HOLD_TRIAL_TOPOLOGY`: stop pursuing the first sample until the complete experiment is feasible. Retain authorization and the unstarted 14-day window. |
| Contextual memory | Two bounded offline increments and the answer baseline completed on 09/08. | Remains complete for this iteration. Future real failures may justify a narrow correction; there is no current collection clock. |

Missing observer history or owner labels does not prove that no use or
subjective benefit occurred. The R4-A rule is two increments without observed
daily-use value; its 30-minute observer limit is a per-session bound. R7 has
no calendar collection deadline, and its report freshness bounds are not
collection-window limits. No fixed maximum authorization-to-first-event wait
was specified for R4.

## R4: preserve authorization, hold the incomplete experiment

The retained kickoff is `LIVE_KICKOFF_ADMISSION_PASS`, bound to source
`19fe2cedca1f1a609af83fae0da1977a3a7f691c` and one canonical Mac writer. Its
SHA-256 is
`9a395a094a2433c0d220e141c1280ccd17905d740835970e202e1e4355ce1b0d`.
The salted node digest is an operator assertion, not independently recomputed
identity proof. This documented V1 limitation does not revoke authorization.

The read-only entry investigation found:

- The exact ledger parent is owner-owned, mode `0700`, and passes write and
  search access checks. No write was attempted; first-append durability was
  not retested.
- Python 3.9.6 and byte-identical kickoff-bound script/specification exist in
  four inspected Mac worktrees. The old primary checkout lacks them, so it
  must not be treated as the sole usable entry.
- The inspected agent instructions lack R4 authorization, exact-ledger, and
  foreground recording responsibility routing. This is an entry gap; without
  a historical missed-event audit it is not a proven cause of all stagnation.
- The [frozen reducer](../../../scripts/agent-bridge-benefit-dogfood.py) accepts
  `linux_avatar_live_receipt` plus `linux_avatar_live_observation` for Avatar,
  and a Qwen3 voice subreceipt from that Linux envelope. The bound live producer
  requires Linux with `linux-native-avatar`; the inspected Mac has a native
  Darwin executable. Its installed Qwen worker, Python, and socket do not
  establish a compatible receipt producer or prove current audible use.
- The kickoff has no explicit cross-node source-receipt arrangement. The
  [V1 contract](../../BENEFIT-DOGFOOD-V1.md) leaves that arrangement to a live
  kickoff decision. `cross_node_writes=false` neither authorizes receipt
  transport nor proves every possible topology was denied.

Fixing only the recording instructions could start the shared clock with a
continuity row while two locked gates still lack an admitted source. This
closeout therefore records the blocker and adds status routing; it does not
add a producer, lower a gate, migrate the writer, or transport receipts.

Reconsider R4 only when a naturally useful workflow provides a concrete,
compatible source plan for **all four existing gates**. First review that plan
against the retained kickoff and original boundaries. Reuse authorization for
the same admitted action; a materially different source topology or replacement
trial requires a concrete amendment at that boundary. Once feasible, the
working agent can repair the foreground route using the exact bound ledger.
Do not start the window merely to test the route.

The first eligible accepted row alone sets `starts_at`; `ends_at` remains
`starts_at + 1209600` seconds, with no automatic extension. The four Linux
legacy continuity rows are all from 08/26, on another ledger before formal
authorization. They remain separate and cannot be backfilled or merged.

The V1 specification, script, and tests still match their kickoff hashes.
All four original bound artifacts remain available at `19fe2ced`; the current
CI workflow has a later hash and is not substituted into that binding. This
closeout changes none of these files. The specification's source-stage
"authorization pending" description is historical; this report and the
current decision board record the actual live state. No kickoff hash or
start/end field is rewritten.

## R7: stop pursuing an incomplete foreground route

The [shadow evaluator](../../../crates/bridge/src/resident_m2_shadow.rs)
always adds a suppression reason for an active or unknown foreground owner
session. `would_wake` is true only when there are no suppression reasons.
An ongoing owner conversation must be labeled active under the
[foreground procedure](../../operations/R7_ASSISTED_SHADOW_COLLECTION.md).
Repeated samples from this path cannot supply the required natural
`would_wake=true` result.

This is a limit of the foreground-active path, not proof that all candidate
paths are impossible. The CLI accepts truthful inactive inputs. A timely,
verified recovery, warning/critical failure, or explicit due commitment may
pass when basis, quiet hours, freshness, deduplication, interval, and budget
requirements also hold. No admitted natural inactive workflow was demonstrated
by this review.

The anchored Mac gate still lacks two natural reports, a second natural
trigger kind, and one natural true decision. Four legacy Linux reports have
no current ledger identity/anchors and do not fill that denominator. Matching
bytes for the previously described natural recovery were found on Linux;
"missing everywhere" is no longer accurate, but cross-ledger admission does
not follow.

Reopen active pursuit only if an already-admitted real task independently
produces a costly, qualifying event while the owner foreground session is
truly inactive, and an existing admitted entry can submit it promptly. No
manufactured failure, delayed active event, invented inactivity, scheduler,
new collector, or relaxed threshold is a substitute. Ordinary foreground
diagnostics remain available within their existing scope and do not automatically
reopen this goal. Repairs and documentation are not additional value increments;
elapsed time alone does not prove the two-increment refreeze rule fired for R7.

## R4-A and ongoing work

R4-A's two delivered increments remain available for explicit foreground use.
Freeze ends the active collection campaign, third-increment pursuit, and
observer expansion. Reopen only for a recurring natural need with measurable
owner cost and a bounded next action; an already admitted session can still
receive an owner helpful/neutral/distracting label when used naturally. There
is no routine prompt to use the feature just to fill a ledger.

The working agent owns these decisions and their handoff. Held lanes receive
at most the existing 15-minute weekly portfolio review, or an earlier review
when a stated trigger actually occurs. There is no new timer or standing
sample-acquisition task. Ordinary development and correction of meaningful
missing/stale/harmful recall continue through the retained workflow.

## Evidence custody and validation

The local audit files are retained under
`/Data/CascadeProjects/.analysis-reports/ab-collection-window-audit-20260908/`;
the entry diagnosis is under sibling directory
`ab-validation-closeout-20260908/`. They contain bounded inspection results,
not natural validation samples. The published report records only the facts
needed for the decision; no raw owner authorization text, node-identity
preimage, or private event body is copied into source.

| Local audit file | SHA-256 |
| --- | --- |
| `r4a-evidence.json` | `dad9e58eb9b9d80fbb09405708cf3eaa11c87ca9222f95357e8a397abf6c234e` |
| `r7-evidence.json` | `85c824a0f00743732224710ff1baff20bc4d27dd3fdd1e04e5273a6f0f64c574` |
| `mac-r4-kickoff-evidence.json` | `d84232a9dcc82c2a4186f21ad4252cee8e3fa62568b014e91f055f21ad82e523` |
| `linux-r4-legacy-evidence.json` | `e5eacc3a0fe4f9f9ea3404b7540b908bc26657de071188d22e907c7dfb03f789` |
| `r4-entry-diagnosis.json` | `d6061a6e9efba11fe08ef343933e7ad6f71ce3dd0b78dfa1cefb508484de190a` |

Validation for this change is documentation/link consistency, independent
source and decision review, preserved kickoff-bound artifacts, and
`git diff --check`. No runtime rebuild or natural trial is needed to enact
these product dispositions. Existing ledgers and the original audit remain
historical evidence. Obsolete active collection scratchpads are retired only
after their content and this current decision are preserved in durable handoff.
