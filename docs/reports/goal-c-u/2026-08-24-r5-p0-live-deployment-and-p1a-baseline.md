# R5 P0 live deployment and P1a baseline

P0 activation snapshot captured: 2026-08-24 (America/Los_Angeles)

## P0 deployment evidence

- Beneficiary-closure source merge: `de0ef4ebb9202ec1cae378954a3b2b50ef0ccbd0`.
- Installed source descendant: `bab5d97e3a1ecfde8b327fd84215b43dbe83805a`.
- Installed version: `agent-bridge 0.14.0
  (v0.14.0-1837-gbab5d97e; bab5d97e3a1e)`.
- Installed `.real` SHA-256:
  `e5e9bc96e543168a43b1184e4c418065c1c18ec01fb73f2120bd80d02f4ac169`.
- Wrapper SHA-256 remained
  `455a73945bfb85966f956df5b16320cedc02ec9dfda997d6d4419fff74c66bae`.
- Daemon, daemon-http, and Palace were restarted on the installed `.real`;
  both HTTP health endpoints returned `ok`.
- Production SQLite schema version is 43. The pre-migration backup named
  `state-before-beneficiary-closure-de0ef4eb-20260824T080930-0700.db` passed
  integrity check and has SHA-256
  `33347d0f2648ad78df79966a88835fc98d8453206cb7151e8a5ffd5f3992d8f9`.

Debug validation before deployment passed the world-core, store outcome,
store operation-receipt, task-outcome, session-finalize, scorecard, and
operation-receipt suites plus `cargo check`. Copied-live and fresh-store
behavior smokes passed in debug and in the deployment build. This report does
not turn those tests into owner acceptance or authenticated harness evidence.

## First live outcome

The production outcome ledger contains one admitted record:

- outcome ID:
  `beneficiary-closure-v1-p0-deploy-de0ef4eb-bab5d97e-20260824`;
- record digest:
  `sha256:ce0e563aa3deba43c3cbc857322f5e344094915877e455cd6d4f12d6d1191efe`;
- status `achieved`, verification `verified/tests`, rollback `available`;
- provenance `agent_reported`; and
- acceptance `unknown` / provenance `unavailable`.

The first seven-day live scorecard read after the Codex restart attempt
reported 1 input record, 1 admitted record, 0 invalid records, 0 conflicts,
100% reported verification coverage, 0 owner-accepted claims, and complete
coverage for all three operator-burden fields. The receipt ledger contained
zero rows. These are provenance-labeled claims and counts, not proof of task
truth or user benefit. In particular, scorecard zeros describe the persisted
input set; the current ledger does not retain rejected attempts and therefore
cannot prove that no invalid or conflicting retry was attempted.

## P1a reachability baseline at activation snapshot

The owner's active Codex configuration selects
`codex-essential-mobile-projection` with profile `essential`. A current
installed-binary MCP probe listed 107 tools:

| Surface | Present before P1a |
|---|---:|
| `session_finalize` | yes |
| `practical_workflow_scorecard` | yes |
| `embodiment_record` | no |
| `embodiment_snapshot` | no |

Therefore deployed Codex can record and inspect task outcomes but cannot use
the P0 body-receipt path through its configured compact surface. P1a is
limited to exposing receipt-only forms of the two existing tools in that
profile. The writer must hide and reject legacy Event Spine kinds; the reader
must exclude Event Spine facts, body telemetry, and write-lease state.

The restart attempt did not establish a fresh host-managed MCP child: `doctor`
still found three deleted-inode `.real` children under the same long-running
Codex parent and no current `.real` child. The 107-tool observation above came
from a bounded direct probe of the current installed binary, not from a claim
that the host refresh succeeded. P1 collection must not start until the
freshness prerequisite in `docs/R5-BENEFICIARY-CLOSURE-DOGFOOD.md` is met.

## Later P1a predeployment observation

A later same-day read found that another deployment had replaced the installed
`.real` with source `209514a7c5b2dcb662459fca28d0e9e7b2ee1b74`, SHA-256
`f5ed11ad6333c9cc6002d822afcdc28453b1ee4d81ca44a2277e09b2f087c69d`.
The daemon, daemon-http, and Palace processes still resolved to a deleted
`.real` inode whose `/proc/<pid>/exe` SHA-256 was the earlier
`e5e9bc96e543168a43b1184e4c418065c1c18ec01fb73f2120bd80d02f4ac169`.
`doctor` nevertheless returned `ok=true`/`fails=0` while separately warning
about stale MCP children. This is direct evidence that installed-path identity
plus the current doctor summary is insufficient to prove a particular live
process is current. P1 activation therefore requires matching live executable
identity/hashes as frozen in the dogfood contract.

## Decision

Proceed with P1a evidence reachability and the preregistered real-task trial.
Do not add automatic outcome/receipt generation, Registry or lease machinery,
mutation authority, an adjacent-window scorer, or a second tool-health system
in this increment.
