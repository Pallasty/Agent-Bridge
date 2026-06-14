# BioCortex Retrieval Opt-In Authorization Decision

Date: 2026-06-11

## Decision

Human authorization granted for `opt_in_experiment` implementation work only.

Machine-readable decision record:

- `docs/design/fixtures/biocortex-retrieval-opt-in-authorization-decision-2026-06-11.json`

## Authorized Scope

This authorization allows implementation work for the FTS-only, per-call
opt-in experiment described in:

- `docs/design/BIOCORTEX_RETRIEVAL_OPT_IN_EXPERIMENT_PLAN_2026_06_11.md`
- `docs/design/BIOCORTEX_RETRIEVAL_OPT_IN_AUTHORIZATION_REQUEST_2026_06_11.md`

Allowed implementation scope:

- add the Cargo feature `biocortex-retrieval-opt-in`;
- add the runtime enable env `AB_BIOCORTEX_RETRIEVAL_OPT_IN`;
- add an explicit per-call opt-in surface for FTS only;
- keep `AB_BIOCORTEX_RETRIEVAL_DISABLE` as the kill switch;
- return baseline without feature, runtime enable, and per-call opt-in all
  present;
- return baseline on absent, error, timeout, low coverage, malformed
  side-signal, or operator-disable cases;
- add tests and audit output for the above boundaries.

## Not Authorized

This decision does not authorize:

- default retrieval influence;
- hybrid retrieval influence;
- semantic retrieval influence;
- `runtime_adapter_approved=true`;
- `default_search_order_change_allowed=true`;
- affecting calls that are not explicitly opted in;
- deploying or using the implementation without a post-implementation review.

## Required Next Step

The next implementation step must be feature-gated and reviewable. It should
start with skeleton guardrail tests and inert feature/env plumbing before any
ordering behavior is added.
