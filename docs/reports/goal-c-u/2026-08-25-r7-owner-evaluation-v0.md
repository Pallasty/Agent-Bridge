# R7-E1 Resident owner evaluation v0

Date: 2026-08-25 (America/Los_Angeles)

Status: contract, source, automated tests, debug CLI, isolated real-provider
technical fixture, merge, installed-binary deployment, and one owner-visible
unevaluated wake passed. The explicit owner product label is the only remaining
gate; no such label is claimed by this record.

## Measured gap

R7 M1 correctly stored every new provider digest with
`owner_acceptance="unknown"` and documented the four permitted owner labels.
Code and durable-state inspection found no command or API that could bind such
a label to a completed wake. Therefore the product gate could be described but
not closed without an unaudited out-of-band assertion.

## Delivered closure

- `agent-bridge resident evaluate --wake-id ... --label ...` accepts exactly
  `useful`, `neutral`, `distracting`, or `harmful`.
- `--dry-run` is state-free, records nothing, and does not claim wake binding.
- Live evaluation requires an existing completed Resident Xiao Shu wake and
  binds to its final-output and execution-receipt hashes plus disposition.
- The authoritative receipt is a 0600 no-replace JSON record under a 0700
  private `evaluations` directory. Complete temporary bytes are synced before
  an atomic no-overwrite link publishes the final path, preventing a
  half-written final receipt. It contains no raw event, prompt, model
  transcript/result text, arbitrary note, or owner identity content.
- Same-label replay returns the original receipt as `already_recorded`.
  Conflicting labels and altered wake hashes fail closed without overwrite.
- The next explicit cognition restores the prior wake's label onto the prior
  sleep digest. Its own new digest remains `unknown` until separately labeled.
- The receipt says only `explicit_local_cli_argument`; it does not claim
  cryptographic owner authentication. Provider/model involvement is false.
- No evaluation path creates a wake, invokes Codex, executes an action,
  changes runtime state, promotes memory, or admits M2.

## Decision semantics

- `useful`: positive M1 signal; only a separate owner review of an M2
  shadow-design proposal becomes eligible.
- `neutral`: retain explicit M1 and do not expand.
- `distracting`: trigger the existing stop rule and prepare a disable review.
- `harmful`: trigger the existing stop rule and prepare a rollback review.

The command records recommendations but executes none of them.

## Automated verification

`cargo test -j 1 -p ab-bridge resident_ --no-default-features --lib` first
passed 14/14 R7 tests and, after deployment exposed the host's non-POSIX home
mount, passed 17/17 with three durable-state-root regressions. Coverage
verifies:

- dry-run with a nonexistent state root leaves it absent;
- missing and failed wakes cannot be evaluated;
- a completed wake produces a private hash-bound receipt;
- identical replay is idempotent and conflicting replay fails closed;
- altered wake hashes invalidate the evaluation binding; and
- an evaluated label is recovered on the prior digest while the next result
  remains unevaluated;
- an explicit `AGENT_BRIDGE_STATE_DIR` takes precedence over XDG state and the
  database parent; and
- XDG state takes precedence over the compatibility database-parent fallback.

The locked no-default-features check and debug CLI build passed. New R7-E1 code
introduced no warnings; the build retained only pre-existing repository
warnings.

## Isolated real-provider technical fixture

The technical fixture used a separate XDG state root and real bounded Codex
provider. Its fixed `neutral` label validates mechanics only and is not an
owner product judgment.

1. The first wake completed in 16,611 ms as `respond`, with zero provider tool
   events, child exit observed, and a verified cognition receipt. Its wake ID
   was `wake-cfc57d6a970e89a856571e027c46e7d4`.
2. `resident evaluate --label neutral` returned `recorded`; all subject,
   journal-state, final-output-hash, and execution-receipt-hash bindings were
   true. The decision remained `retain_explicit_m1_without_expansion`.
3. Repeating `neutral` returned `already_recorded` with the exact same
   receipt. Requesting `harmful` exited non-zero with
   `resident_owner_evaluation_conflict`; the neutral receipt remained intact.
4. The evaluation directory and receipt modes were 0700 and 0600. Receipt
   SHA-256 was
   `cc128b4655b63b8ace49947f7e4fdc665d42ab761752e780b826d80ca49a6413`.
5. A second fresh cognition completed in 18,292 ms, recovered the prior digest
   hash, retained zero provider tool events, and left its new
   `owner_acceptance` at `unknown`.
6. The isolated ledger contained two `cognition_completed/verified` rows.
   Full-text search found neither raw technical event in AB state, no provider
   temporary directory remained, and SQLite SHA-256 was
   `4ff8dc4ae6326880944b8ddb055a1ab6208c4809ebc9f72480cef7445ad98182`.

The installed binary then recorded the second technical wake's fixed
`neutral` fixture through the same CLI. The receipt remained mode 0600 with one
link, the evaluation directory remained 0700, no temporary file remained, and
its SHA-256 was
`4607b9e005f8957e59a045985861b260603d11b60a4fb8d260f5f45640581604`.

## Deployment and installed acceptance

- The feature implementation merged as `bf2106e4f7cb067c054a5244decf0f0243faa52d`.
- The first installed acceptance correctly failed closed before any production
  wake because the historical default home data directory was on `fuseblk` and
  contained only a root-owned, mode-0777, zero-byte writer lock. That empty
  directory was preserved as a timestamped backup; no wake or owner evaluation
  was lost.
- The compatibility fix makes the wake lock, wake journal, and evaluation
  receipt honor the wrapper's common `AGENT_BRIDGE_STATE_DIR`, then XDG state,
  before retaining the old database-parent fallback. It merged and deployed
  from `master` as `cb01c6d603d81dc7bbc20c787ee29d54da17a847`.
- The release build completed in 9 minutes 02 seconds. The installed binary
  reports `agent-bridge 0.14.0 (v0.14.0-1859-gcb01c6d6; cb01c6d603d8)` and has
  SHA-256
  `463015b61461c2d1a13567f295dcea2f91ef10d55a8eb682cf5aa4d5f33e5342`.
- Daemon, daemon-http, and Palace were restarted onto that exact binary.
  `agent-bridge doctor --json` then reported zero failures and zero warnings.
- The installed wrapper selected `/Data/.agent-bridge-state`; the production
  Resident root and wake directory enforce 0700, and journal records/lock
  enforce 0600.

## Owner-visible unevaluated wake

Installed wake `wake-ef3781a1c2fe8366bd31a421a8b1a6ae` completed in 24,159 ms
as `respond`. The provider observed zero tool events, exited with code 0, and
its child exit was observed. The bounded reflection said the closure should be
accepted only when the exact artifact hash, the scope excluding M2, and
reversible inspection evidence are presented together; otherwise it should
remain advisory and unevaluated. The deployment evidence above supplies those
three facts without changing the reflection itself.

The wake journal SHA-256 is
`804b2bda98e116004dbc874d26a3045b0e6cd8199ea02fcf99eef3eed8a339cf`.
Full-text inspection found no raw event in the private state root or SQLite
files. No evaluation receipt exists for this wake, and its sleep digest remains
`owner_acceptance="unknown"`.

## Remaining owner gate

Present the installed result and wake ID to the owner. Only the owner's
subsequent explicit `useful`, `neutral`, `distracting`, or `harmful` answer may
be written to the production evaluation receipt. Until then, product value and
M2 admission remain unknown/closed.
