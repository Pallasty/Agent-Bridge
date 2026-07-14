# BioCortex / AB Track B live-binding ledger

Date: 2026-07-14

Status: **inventory complete for its declared scope; real-run admission remains blocked**

Baseline source: `f19ec1a813ceb2d29be0a74a430293d8b998a574`

## Technical summary

The next safe unit is a non-admitting binding ledger, not a real benchmark.
Within the declared sentinel inventory scope, the frozen Track B contract has
**91 missing scalar paths**: 89 values marked `UNSET_BLOCKS_REAL_RUN` plus two
effective-environment values marked literal `UNSET`. This is not a count of
every semantic blocker in the contract. Its staged protocol also names four
later obligations that do not have dedicated scalar binding fields.

The ledger covers those 91 scalar paths exactly once and separately records the
four declared stage obligations. It does not resolve any of them:
`contract_binding_satisfied_count=0`,
`real_binding_evidence_count=0`, every authority bit remains false, and no
side effect is unlocked.

Current public code and fixtures provide 24 hash-bound supporting artifacts.
They establish source identity, public synthetic mechanism behavior, frozen
protocol history, or static blocker evidence only. Every supporting row has
`may_satisfy_live_binding=false`.

## Local provenance is classified; readiness is not asserted

| Responsibility class | Missing scalar bindings | What can happen next |
|---|---:|---|
| local deterministic | 27 | 23 ultimately require exact trial-specific committed artifacts; 4 derived artifacts remain explicitly upstream-blocked |
| owner policy | 23 | Freeze scientific and operational choices; local code may not invent them |
| custodian private | 25 | Create only under sampling, blinding, privacy, and review custody |
| authorized runtime capture | 16 | Derive only from the frozen binary, snapshot, hardware, generator, or storage run |
| **Total** | **91** | **Zero are satisfied by this packet** |

The four locally computable but upstream-blocked paths are:

- candidate context builder, until the candidate store adapter is admitted;
- latency total unit count, until the final case count exists;
- required primary case count, until the power analysis exists;
- storage arm-builder identity/procedure manifest, until the candidate builder
  interface is frozen.

Here `arm_builder_manifest_sha256` means a pre-run builder identity and
procedure manifest, distinct from the per-arm runtime measurement manifest.
That distinction keeps it local-deterministic but upstream-blocked.

The other 23 paths identify local artifact provenance, not scheduling
readiness. Each must first pass its own dependency check for owner policy,
private interfaces, and upstream schemas; when it is ready, the only valid
binding is the exact new artifact named by the trial with committed bytes. A
nearby source file, the public fixture, or a consumed successor-v3 artifact is
supporting material, not a substitute binding.

A chart is intentionally omitted: this is an exact small-category audit where
the table preserves the authoritative counts and action boundary more clearly.

## The old preregistration is correctly stale at current HEAD

The frozen v0 admission packet remains byte-identical, but three of its eleven
source bindings have changed since the packet was created:

- `crates/bridge/src/mcp_tools.rs`;
- `crates/store/src/lib.rs`;
- `crates/store/src/sqlite.rs`.

Eight source hashes still match and three drift. Running the original checker
against the current source therefore fails closed. This is the expected result
after the reference determinism work; it is not evidence that S0 regressed, and
the old receipt must not be rebound in place.

The new ledger records the old packet as
`FROZEN_PROTOCOL_BASELINE_ONLY`. A future admission must use a new schema and
new live evidence rather than revise history until the old receipt appears
green.

## Stage coverage is explicit, not overstated

The 91 scalar rows split into:

| Required stage | Scalar rows | Additional declared obligations | Current state |
|---|---:|---:|---|
| pre-output admission | 87 | 0 | blocked |
| post-generation, pre-review | 4 | 1 map-bijection receipt without a dedicated field | not reached |
| pre-unblind | 0 | 3 review-chain / score-claim symbols without dedicated fields | not reached |

Thus `inventory_complete=true` means only
`CONTRACT_SENTINELS_PLUS_AMBIENT_ENV_AND_DECLARED_STAGE_OBLIGATIONS` is fully
inventoried. It never means that admission bindings or all stages are complete.

The two literal `UNSET` environment entries are counted separately because
the old receipt counted only the 89 longer sentinels. They are policy choices,
not silently resolved defaults.

## Evidence and metric definitions

The analytical grain is one exact dotted contract path. A valid inventory must
satisfy all of the following:

- completeness: the contract's current 89 blocking sentinels and two ambient
  unsets equal the ledger's 91 rows;
- uniqueness: every binding path occurs once;
- validity: 72 SHA-256 bindings and 19 non-hash values retain the correct value
  kind;
- consistency: owner-class, local-fill, section, and required-stage counts all
  match the frozen classification catalog;
- integrity: each of the 24 supporting files is a canonical repo-relative,
  regular, non-symlink, non-hardlinked file with the recorded SHA-256;
- timeliness: the ledger is anchored to the current baseline, while the old
  contract's three expected source drifts remain visible rather than hidden.

The classification catalog and supporting-material catalog have independent
hashes. This prevents a self-consistent edit from reclassifying a private or
runtime field as local, or replacing an allowed support artifact with another
tracked file and recomputing only its row hash.

## Enforcement and robustness checks

The strict checker:

- rejects duplicate JSON keys, non-canonical JSON, type drift, path aliases,
  symlinks, hardlinks, missing files, and source-hash changes;
- requires every row to keep `binding_satisfied=false`,
  `binding_evidence=null`, and `unlocks_side_effect=false`;
- freezes all four responsibility classes, two required stages, the four
  unrepresented obligations, and all authority bits;
- independently observes the original contract's 8 matching and 3 drifted
  source bindings;
- has no `--admit` or upgrade mode.

Its adversarial self-test rejects 40 mutations, including full classification
rebinding, full supporting-artifact rebinding, false authority, omitted ambient
unsets, premature stage advancement, fake evidence, and changes to the frozen
contract obligations.

The shell gate runs the checker twice from immutable HEAD blobs, compares both
outputs with the fixed receipt, runs the adversarial self-test, verifies exact
Git paths and modes, and fences HEAD, index flags, replace refs, and worktree
changes.

## Limitations and non-authority boundary

This packet does not open the owner database, read a private frame or blind map,
build a runtime binary, select a tokenizer, invoke a generator or reviewer,
measure hardware, inspect a real storage package, or create truth authority.
It cannot support a latency, storage, retrieval-quality, application-value, or
scientific claim.

The S0 reference surface and its public fixture are useful mechanism evidence,
but the store example is not the final paired MCP runner. Fixture limits such as
16 KiB and source defaults such as 128 KiB do not become the real per-case
budget. Consumed successor-v3 schemas, cases, reviewers, secrets, maps, and
results remain inadmissible; only implementation patterns may be reused.

The preregistered date 2026-07-17 is a lower time boundary, not an authorization.
Reaching that date does not fill a single binding or unlock a side effect.

## Recommended next implementation slice

After this ledger is source-bound and merged, turn the 23 exact-artifact paths
into an explicit dependency graph. Start only the subset whose policy and
interface prerequisites are already frozen:

1. strict review, sampling-receipt, truth-manifest, referent, and strict-case
   schemas plus their provenance / bijection checkers;
2. paired estimator, seed-derivation, selection, frame-builder, serializer, and
   real-run harness source artifacts;
3. the exact context builder and tokenizer code surface, while leaving
   tokenizer identity and byte/token budgets to the owner-policy packet and
   the tokenizer model-byte hash to authorized runtime capture.

These artifacts should remain `PLANNED_NOT_BOUND` until a new admission schema
binds their exact committed bytes together with the 64 owner, custodian, and
runtime inputs. The next external handoff should therefore be a three-part
request: owner decisions, custodian-private artifact plan, and authorized
runtime capture plan.

## Further questions

A later admission packet still needs named owners for the 23 owner-policy paths,
a fresh custodian and reviewer roster for the 25 private bindings, and an
authorized machine/snapshot window for the 16 runtime bindings. Those choices
can change scheduling, but they do not change the current fail-closed decision.

## Verification

Run:

```bash
./scripts/check-biocortex-ab-track-b-live-binding-ledger.sh
```

A successful gate reports a complete inventory while still emitting:

```text
decision=BLOCKED_FAIL_CLOSED
real_run_admitted=false
capture_allowed=false
contract_binding_satisfied_count=0
all_stage_admission_complete=false
```
