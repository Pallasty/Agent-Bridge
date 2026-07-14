# BioCortex / AB reference admission fixture

Date: 2026-07-14

Status: **public synthetic fixture PASS; real capture remains blocked**

## Scope

This fixture exercises the explicit read-only reference surface added by S0.
It does not open the owner store, call an MCP tool, invoke BioCortex, run a
generator, or qualify any memory row as truth evidence. `fixture_only=true`,
`real_capture_authorized=false`, and the receipt decision is
`BLOCKED_FAIL_CLOSED`.

## Bound fixture

- Fixture: `scripts/eval/fixtures/biocortex_ab_reference_admission_v1.json`
- Fixture SHA-256:
  `a2d8718e5982b030659f20c69a893ec4d1e39f3b10b01fdd960df0ac55f9af4d`
- Expected receipt:
  `scripts/eval/fixtures/biocortex_ab_reference_admission.expected.v1.tsv`
- Expected receipt SHA-256:
  `04bfaf10a8bf343ff133b46388ea798ee81e6fd605198d6a48f84ea9236cc32c`
- Implementation/source identity: the gate binds and emits the current clean
  `HEAD`. A fixed commit is deliberately not embedded in this tracked report,
  because changing the report would create a different `HEAD`.

The input has fixed memory rows, ordinary graph edges, actual
`memory_coactivation` counts, a frozen `as_of_secs` value, a 5-edge graph
fan-out, a 16 KiB exact UTF-8 context budget, and an exact one-day TTL boundary.
Three fresh temporary SQLite clones use the same fixture bytes but reverse
memory, graph-edge, and coactivation-spec insertion order in two clones.

## Assertions

The runner requires all of these to hold in every clone and on a repeated run:

1. equal-score `tie_a`/`tie_b` order is binary-key deterministic;
2. the seed projection is exactly `seed_anchor`, `graph_neighbor_3`, then
   `graph_neighbor_0..2`; graph expansion is capped before the excluded `skill`
   row is removed, so later neighbours are not admitted;
3. the `skill_excluded` row never enters the final context;
4. one second before expiry, both the `ttl:1d` and `ttl:2d` controls survive;
   at exact one-day expiry, the `ttl:1d` control is removed while `ttl:2d`
   survives, through `memory_search_reference` and the shared TTL policy;
5. the projected context stays within `UTF8_BYTES_V0` and contains no `score`,
   `importance`, `access_count`, or `last_accessed_at` field;
6. graph-only reads leave `last_accessed_at` and `access_count` unchanged;
7. real coactivation counts are written through `record_coactivation`; reversing
   their insertion order does not change the projection, while disabling the
   coactivation reranker does change the order and proves the control is live;
8. the three fresh clones and two full runner executions produce identical
   byte strings;
9. the runner clears every inherited exported variable with shell builtins,
   then admits only toolchain paths and the frozen reference policy; the three
   hostile `AB_*`, `AGENT_BRIDGE_*`, and `RUST_LOG` sentinels are independently
   checked as absent by the Rust example (`sentinels_cleared=true`).

## Verification

The source-bound gate is:

```bash
./scripts/check-biocortex-ab-reference-admission.sh
```

It runs the clean-environment runner twice, compares both stdout streams to the
fixed receipt, checks the exact fixture and runner modes, and fences `HEAD`,
tracked-worktree, and index drift. A passing invocation emits this receipt
shape, with `head` resolved from the committed tree at execution time:

```text
BOUND_TO_HEAD_BIOCORTEX_AB_REFERENCE_ADMISSION_FIXTURE
head=<current clean HEAD>
fixture_sha256=a2d8718e5982b030659f20c69a893ec4d1e39f3b10b01fdd960df0ac55f9af4d
receipt_sha256=04bfaf10a8bf343ff133b46388ea798ee81e6fd605198d6a48f84ea9236cc32c
fresh_clones=3
repeated_runs=2
real_capture_authorized=false
decision=BLOCKED_FAIL_CLOSED
```

This is mechanism evidence only. Exact BioCortex binary/source identity, a
closed private snapshot, a live prevalence frame, frozen tokenizer identity,
hardware/storage manifest, reviewer provenance, blind map, and a qualified
truth-authority substrate remain unset. The fixture therefore cannot authorize
a real BioCortex capture or support a performance/scientific claim. The Track B
admission gate remains an independent fail-closed authority check.
