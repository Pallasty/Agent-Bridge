# CLI composition-root governance receipts

S14-B requires one receipt in this directory whenever a proposed diff changes
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
