# CLI composition-root governance receipts

S14-B requires a bound receipt for each transition whenever a proposed diff changes
`crates/bridge/src/main.rs`. The receipt binds the exact file before and after
the change, classifies every changed region, and records the behavioral
contracts checked for that change.

Run the gate against the branch or commit that the work started from:

```sh
scripts/check-cli-composition-root-governance.sh <base-ref> [head-ref]
```

Generate the binding values with:

```sh
git rev-parse <base-ref>
git show <base-ref>:crates/bridge/src/main.rs | shasum -a 256
shasum -a 256 crates/bridge/src/main.rs
```

Copy `receipt-v0.example.json` to a descriptive dated filename in this
directory and replace every placeholder. Evidence entries must identify an
actual test, snapshot, source boundary, or explicit not-applicable reason.

The four classifications are:

- `cli_schema_or_routing`
- `startup_or_dependency_injection`
- `authority_or_effect_adapter`
- `pure_logic`

Pure logic must be `extracted` or carry a reviewed `exception` with an
`exception_reason`; it cannot be admitted as `root_visible`. Authority/effect
changes require the `authority_and_effect_ordering` contract to be `passed`.
Every `root_visible` entry requires a `root_reason` explaining why the
composition root must retain that code.

The receipt is governance evidence, not permission to add authority, enable a
runtime, deploy a build, or skip normal tests.

## Staged commits and comparison-base changes (2026-09-13)

Install the tracked hooks with `bash scripts/install-githooks.sh`. Pre-commit runs
`python3 scripts/eval/cli_composition_root_governance.py validate --base HEAD
--head INDEX` before the Rust check. Only staged main.rs and staged receipts
count. This local check works when CI is intentionally skipped. Hooks can be
bypassed explicitly and do not constitute server-side branch protection.

The source_base is still an exact full commit SHA and must be an ancestor of
the candidate. Its before digest must match that commit's main.rs. A comparison
base may advance through unrelated changes with identical main.rs content.
Multi-commit pushes/PRs can supply multiple changed receipts only if their
hash edges connect the exact comparison file to the proposed file without a
gap or dangling edge. Each receipt continues to classify its own change.
Use a fresh dated receipt for each source change rather than overwriting an
older receipt. Receipt-only changes are checked too, so they cannot silently
corrupt the evidence.

Do not repair a historical missing receipt by weakening the hash checks.
Record a retrospective current-source audit and start a fresh bound transition;
that does not make an earlier commit's admission green. See the S16/S17 ADR
for the S15 publication gap and post-S15 audit.

A reviewed retrospective repair can prepend an ancestor-bound receipt chain
ending at the comparison base. It cannot stand in for the forward receipt of
an incoming main.rs change. This permits a current correction of an old
receipt and a dated audit of previously uncovered changes without rewriting
Git history or pretending the old gate passed. See the 2026-09-13 receipts.
