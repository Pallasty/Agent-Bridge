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

- Fixture: `scripts/eval/fixtures/biocortex_ab_reference_admission_v0.json`
- Fixture SHA-256: `9045999ee6e0b8b4fab884684820eb8ab26c3a26f628a264fa90ee065d8e67c8`
- Expected receipt:
  `scripts/eval/fixtures/biocortex_ab_reference_admission.expected.v0.tsv`
- Expected receipt SHA-256:
  `b253e4873300d9d357e51eb1a6b2531867acedbd4dfec1db92cbf4f67418d8a0`
- Source HEAD during the gate: `ad0c688504b317d066a1edd8d4e5d24dade3682b`

The input has fixed memory rows, edge rows, an `as_of_secs` value, a 5-edge
graph fan-out, a 16 KiB exact UTF-8 context budget, and a one-day timestamp
boundary. Three fresh temporary SQLite clones use the same bytes but reverse
memory/edge insertion order in two clones. Coactivation edge order is therefore
an input-order perturbation, not a hidden live sidecar.

## Assertions

The runner requires all of these to hold in every clone and on a repeated run:

1. equal-score `tie_a`/`tie_b` order is key-deterministic;
2. the seed projection is exactly `seed_anchor` followed by four bounded graph
   neighbours; the sixth edge is not admitted by `graph_fanout=5`;
3. the `skill_excluded` row never enters the final context;
4. the frozen `as_of` timestamp gives the same `ttl_boundary`/`ttl_after_boundary`
   order on every replay (this observes the boundary; it is not a claim that
   the reference surface currently owns a TTL policy);
5. the projected context is exactly within `UTF8_BYTES_V0` and contains no
   `score`, `access_count`, or `last_accessed_at` field;
6. graph-only reads leave `last_accessed_at` and `access_count` unchanged;
7. reversed coactivation insertion order and repeated fresh clones produce the
   same projection byte string;
8. an `AB_*`/`AGENT_BRIDGE_*`/`RUST_LOG` hostile environment does not reach the
   Rust example; the receipt reports `sentinel_cleared=true`.

## Verification

The direct gate is:

```bash
./scripts/check-biocortex-ab-reference-admission.sh
```

It runs the clean-environment runner twice, compares both stdout streams to the
fixed receipt, checks the exact fixture/runner modes, and fences HEAD, tracked
worktree and index drift. The observed receipt is:

```text
BOUND_TO_HEAD_BIOCORTEX_AB_REFERENCE_ADMISSION_FIXTURE
head=ad0c688504b317d066a1edd8d4e5d24dade3682b
fixture_sha256=9045999ee6e0b8b4fab884684820eb8ab26c3a26f628a264fa90ee065d8e67c8
receipt_sha256=b253e4873300d9d357e51eb1a6b2531867acedbd4dfec1db92cbf4f67418d8a0
fresh_clones=3
repeated_runs=2
real_capture_authorized=false
decision=BLOCKED_FAIL_CLOSED
```

This is mechanism evidence only. The exact binary/source identity, closed
private snapshot, live prevalence frame, frozen tokenizer, hardware/storage
manifest, reviewer provenance, blind map, and truth-authority substrate remain
unset. The old Track B packet consequently continues to reject the changed
store source hash, as required by fail-closed admission.
