# Engram G1.3 Corpus-Freeze Review Gate Result

Date: 2026-07-18

Status: **PASS / PRIVATE FREEZE REVIEW ONLY**

## Result

The G1.3 public contract, owner-to-manifest input-chain validator, two-reviewer
freeze validator, custody validator, and synthetic negative suite pass. The
gate fixes the future freeze decision before any new private corpus is
assembled.

No real role, review, owner-decision, corpus manifest, or freeze evidence was
found or created. No raw query, target key, episode-group membership,
partition membership, identity, or sealed material was read into the public
artifacts.

## Binding

- G1.1 preflight commit:
  `3256fe024c2a280bcd4ac0fee4ff79563c0cc36a`;
- G1.1 contract SHA-256:
  `5d4835fa2aa404224b98e7a60574121118051d771079f5a0422ab5839564e94a`;
- G1.1 validator SHA-256:
  `f276765f22ee5b2f69e24cf7a79bd9a30e8291f900973d89c06f17d1d0468cdc`;
- G1.2 role-review commit:
  `426560f67369ec5851b4813fe31a3fe12ae4adde`;
- G1.2 contract SHA-256:
  `efb7464e2922d0dd2645698435272714316d07f786bd5a56114e900b99e31f6c`;
- G1.2 validator SHA-256:
  `5efe72815341492b84a4bd0dee487d1eb572e60e7938f3df7e5cb9710ef8706f`;
- G1.3 contract SHA-256:
  `885ad2c0a0590631b1a4c33e168bffd5e1153039a1b5325a24c343599c5c35b5`;
- G1.3 validator SHA-256:
  `e018a1af2bb0aa93af4868787a0cc186164a5661cf306549a0dfe42aa6f9d657`;
- G1.3 checker SHA-256:
  `577a5e02e380858a452e8edb4c030c677d30cd53ceedaf86ab784f765ea194b6`.

The predecessor files remain unchanged. G1.3 loads and hashes both predecessor
validators before it accepts their packet types.

## Structural proof

The positive synthetic chain contains five distinct role holders, an
application-owner approval, an outside independence audit, an owner assembly
decision, a complete 30-group manifest with 540 baseline observations, two
appointed freeze-review approvals, and matching sealed custody.

Its final verdict is `SYNTHETIC_FREEZE_APPROVAL_VALID_NO_AUTHORITY`.
Structural approvability is true while every operational authority remains
false.

The mutation suite rejects:

- contract relaxation and manifest substitution permission;
- owner rejection and manifest assembly before owner authorization;
- role, review, owner-decision, or manifest hash drift;
- freeze review starting before manifest assembly;
- candidate, duplicate, or outsider reviewer commitments;
- approval with an incomplete registered check;
- placeholder or duplicate review receipts;
- wrong custodian, receipt reuse, or changed-manifest custody;
- candidate-authored freeze review or raw identity fields;
- real evidence packets outside ignored `data/`;
- duplicate JSON keys.

One reviewer rejection is accepted as a valid rejection receipt and yields no
freeze or next-stage authority.

## Verification

Passed:

- `scripts/check-engram-g0-failure-intake.sh`;
- `scripts/check-engram-g1-corpus-design.sh`;
- `scripts/check-engram-g1-freeze-preflight.sh`;
- `scripts/check-engram-g1-role-review.sh`;
- `scripts/check-engram-g1-corpus-freeze-review.sh`;
- Python compile, Pyflakes, Black, and Bash syntax checks;
- deterministic double-run and outside-working-directory checks;
- redacted-receipt commitment exclusion checks;
- scan of all six changed files against 12 protected G0 query/target literal
  occurrences: zero matches;
- changed-file scan for checked-in real evidence packets: zero files;
- `git diff --check`.

## Authority boundary

The checked-in contract and all synthetic evidence grant no authority. A
future real double-review can freeze only the exact 30-group manifest bytes.
Any addition, removal, substitution, repartition, relabel, or byte change
requires a new review.

Even a real freeze keeps the following false:

- candidate manifest access;
- candidate FIT access;
- candidate implementation;
- BioCortex experiment execution;
- retrieval-order mutation;
- live-store writes;
- runtime promotion.

## Next gate

The next public design gate after a real freeze is candidate-protocol
preregistration: source/configuration hash lock, permitted FIT/development
interfaces, one-shot sealed execution, matched comparator budgets, and explicit
falsifier execution. It must not expose the private manifest or grant code
authority merely because G1.3 exists.
