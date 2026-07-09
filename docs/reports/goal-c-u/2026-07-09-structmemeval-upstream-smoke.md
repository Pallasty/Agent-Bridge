# StructMemEval Pinned Upstream Smoke

Date: 2026-07-09

Source base commit: `e195e1ae`

Run type: network smoke for pinned upstream StructMemEval samples

Parent packet:

- `docs/reports/goal-c-u/2026-07-09-structmemeval-adapter-contract-impl.md`

Upstream source:

- Repo: `https://github.com/yandex-research/StructMemEval`
- Pinned commit: `64d2c9b242deb394e3ef94a318868a55261e141b`
- Default sample loader: `scripts/structmemeval-adapter-contract.py`

## Verdict

The no-write adapter contract helper accepts the three pinned upstream default
samples and emits only hashes, counts, sample projection keys, and a no-write
proof. This is not a benchmark run and does not claim retrieval or answer
accuracy.

## Landed Files

```text
scripts/verify-structmemeval-upstream-smoke.sh
docs/reports/goal-c-u/2026-07-09-structmemeval-upstream-smoke.md
```

## Smoke Result

```yaml
schema: agent_bridge.structmemeval_adapter_contract_impl.v0
source_head: 64d2c9b242deb394e3ef94a318868a55261e141b
input_case_count: 3
session_count: 5
turn_count: 90
query_count: 31
temporary_record_count: 126
temporary_edge_count: 123
reference_answer_shapes:
  array: 1
  object: 30
memory_rows_delta: 0
memory_edges_delta: 0
semantic_events_delta: 0
```

Per-family pinned sample fingerprints:

| family | case_id | sha256 | bytes | sessions | turns | queries | records | edges |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| tree_based | graph_0_trimmed_10_with_path_1 | `644723537360e49395afbf879dd30c7ee31158e46c8b7bb23b83214089ece593` | 15694 | 1 | 10 | 29 | 40 | 39 |
| state_machine_location | static_001 | `de30dbf512fa9fbb8b6c449f98e0cad06382fd7b5ecd0d1a8a310f21b3ed0ece` | 4172 | 3 | 30 | 1 | 34 | 33 |
| accounting | accounting_10__1 | `94cc1e965c43f3a2acb56a8e98306161174b77d34d548f486b6d9f8766d4adf9` | 5546 | 1 | 50 | 1 | 52 | 51 |

## Verification

Commands:

```bash
python3 -m py_compile scripts/structmemeval-adapter-contract.py
bash -n scripts/verify-structmemeval-adapter-contract.sh
bash -n scripts/verify-structmemeval-upstream-smoke.sh
scripts/verify-structmemeval-adapter-contract.sh
scripts/verify-structmemeval-upstream-smoke.sh
git diff --check
```

The upstream smoke verifier:

- creates a temporary SQLite store with sentinel rows in `memories`,
  `memory_edges`, and `semantic_events`;
- runs the helper against its pinned default URLs;
- asserts source commit, source hashes, byte counts, projection counts, and
  no-write deltas;
- asserts output omits raw message/question/reference-answer keys.

## Decision

The pinned-upstream smoke is now a repeatable network check. It should be run
only when network access to GitHub raw content is expected.

The next safe lane is a deterministic answer normalizer design packet for one
family, starting with `accounting` because it has array-shaped settlement
answers and exposes the clearest normalization boundary without needing an LLM
or benchmark runner.
