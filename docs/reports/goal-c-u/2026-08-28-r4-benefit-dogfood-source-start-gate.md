# R4 benefit dogfood source-start gate

Date: 2026-08-28 America/Los_Angeles

Verification time: 2026-08-31T17:10:41Z

Verdict: **SOURCE_START_CONTRACT_PASS; LIVE_COLLECTION_PENDING**

## Scope

The owner authorized implementation of the next reversible R4 gate. This gate
hardens the source-side ledger-path contract and documents evidence admission.
It does not publish source, start live collection, create a dogfood event,
deploy a runtime, or close any of the four value gates.

The current integration baseline is
`a78f1533bf717d34312e59f1111b81ec3a176884`. The integrated R4 implementation
commit is `65c4bdf5953c4cfff5b171c0732466b4e1de0973`; its source artifacts are
byte-identical to the original implementation developed from `cd219d57d3b1`.

## Closed source gate

- Formal collection must bind one new, initially absent, absolute ledger path
  and pass that exact value with `--log` on every command.
- Without `--log`, only an absolute `AGENT_BRIDGE_STATE_DIR` may supply an ad
  hoc diagnostic path. XDG, Linux-home, and macOS Application Support guesses
  were removed.
- Relative paths, `..`, double-root anchors, and state roots that resolve to
  `/` fail closed.
- Only `FileNotFoundError` means an absent ledger. Permission and other open
  failures return `HOLD_INVALID_EVIDENCE` rather than an empty report.
- The start contract distinguishes owner authorization, canonical writer,
  producer freshness, first-event day 0, the exact 14-day window, and end-of-
  window insufficient evidence from the per-event `--attest-real-task` flag.
- Python contract tests now run on explicit Python 3.9 in both Ubuntu and macOS
  CI jobs.

The locked event schemas, sample minima, reducer thresholds, stop conditions,
and runtime non-influence remain unchanged.

## Exact source bindings

| Artifact | SHA-256 |
|---|---|
| `scripts/agent-bridge-benefit-dogfood.py` | `d6712dc4ca73f17e819f34e55624cdefb5030335e8ea6d46dab9dcc4652dc498` |
| `tests/test_agent_bridge_benefit_dogfood.py` | `c7cc82d0654af3558f9d8253e99c5070090c88c67cfdae3e68e20e3ebf069556` |
| `docs/BENEFIT-DOGFOOD-V1.md` | `d2a4fd85e39a525c03504daae91301e4afadefaede5ad34d8ead9ece95434fab` |
| `.github/workflows/ci.yml` | `be32cd935388005b9acbd5efe32b31628a3fa57d76692ddb739f2cea1fe4f633` |

## Verification

```text
Python 3.9.6
python3 -m unittest -v tests.test_agent_bridge_benefit_dogfood
Ran 22 tests: PASS
git diff --check: PASS
```

Additional real CLI checks proved:

- an actually unsearchable ledger parent returns exit 2 with
  `LEDGER_OPEN_FAILED`;
- a genuinely absent explicit ledger returns the zero-event collecting report
  without creating its file or parent;
- `//`, `/..`, and `/tmp/..` state roots fail closed; and
- two independent read-only reviews found no remaining must-fix issue.

The three previously competing `benefit-v1.jsonl` locations and the proposed
dated private-state location were all absent after verification. No formal R4
ledger exists, no `record-*` command ran, and the current event count remains
zero with all four value gates `COLLECTING`.

## Still open

`docs/ACTIVE-PRODUCT-ROADMAP.md` correctly remains `collection pending`.
The next gate is source publication review. A later, separately admitted live
kickoff must bind `authorization_at`, the canonical writer-node digest, one
exact absent ledger path, and the published source bindings. Only the first
post-authorization eligible event may establish the trial window.

No push, merge, deployment, service change, MCP reconnect, automatic producer,
historical backfill, ledger initialization, or live collection is claimed.
