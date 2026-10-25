# Digest natural-use audit — 2026-10-25

Disposition: **bounded read-only diagnosis complete; NO_ADMITTED_CASE;
HOLD_EXTENSION**. No natural-task benefit or absence of harm is established.

## Accepted goal and closure

The owner accepted the preceding proposal with “很好！按照你的思路规划并落地下一目标。”
after the proposal to inspect existing digest/source state, identify a natural
task affected through search/bootstrap, and extend only a demonstrated entry.
This changes the work from adding read protection to measuring its actual need.
The reason is the remaining lack of natural-task evidence, not a change to the
previous local implementation's acceptance. No deployment was requested here.

- Real problem hypothesis: a source-invalid digest can reach task context via
  an entry not covered by the local `memory_get` guard.
- Last-30-day proven occurrences: **unknown**, not zero incidents.
- Owner cost per occurrence: **unknown**.
- Smallest closure: inspect the connected store and existing telemetry, publish
  a supported positive case or a bounded negative/unknown result.
- Work performed: one foreground read-only inventory plus source-path review.
- Consequence of no extension: the known source-level coverage gap remains;
  actual user impact remains unproven.

Acceptance is closed for inventory and entry-path diagnosis. The requested
natural-task linkage could not be established from the available evidence;
it is explicitly **not satisfied**, and no replacement synthetic task was run.
This is a closed diagnostic, not an open sample-pursuit goal.

## Observed scope and method

The connected MCP `capabilities` reports its database as
`/home/pallasting/.agent-bridge-secure/data/agent-bridge/state.db` and build ref
`e32700c1e92f`. This is a backend report, not binary-to-source attestation.
Other stores, hosts, backups and deleted historical content were not audited.

The decisive extraction ran at **2026-10-25 12:09:12 UTC**. Its 30-day window is
2026-09-25 12:09:12 UTC through that instant, inclusive. SQLite was opened with
`mode=ro`, `query_only=ON`, a SQL authorizer permitting only read/transaction
operations, and one read transaction for inventory and telemetry aggregation.
The connection recorded zero changes and zero denied SQL actions. A separate
read-only query cross-checked the main counts. This does not claim that other
processes left the live database bytes unchanged during the audit.

No `memory_search`, `memory_get` or `session_bootstrap` invocation was used to
manufacture exposure. Existing tool surfaces do not supply the required joined
transactional inventory, so local SQL was used after obtaining the database
location from the connected backend. The capability lookup itself can enter
normal tool-call telemetry; it is not a retrieval or natural validation sample.

## Results

| Observation in the connected store | Count | Meaning |
| --- | ---: | --- |
| Retained memory rows | 8,788 | Includes lifecycle markers |
| Active rows | 2,245 | Not a digest count |
| Archived / superseded / tombstoned rows | 1 / 397 / 6,145 | Inventory only; tombstone bodies not inspected |
| `kind=digest` or `kind=digest_draft` | 0 | No typed digest/source set available to classify |
| Kinds containing `digest` | 0 | No alternate digest-named kind found |
| `digest_sources_v1:` binding marker | 0 | No bound-source digest to verify |
| Parsed exact digest/promotion tags | 0 | Tags checked: `digest`, `digest:candidate`, `derived:digest_author` |
| Key/tag substring `digest` candidates | 27 | 16 non-tombstoned; 11 tombstoned metadata rows |
| Malformed tag metadata | 1 | Active decision; no raw binding or author marker; excluded from parsed-tag classification |
| Retained `memory_query_log` rows | 1,732 | Aggregate queries, not per-result source revisions |
| Retained `retrieval_surfacing` rows | 0 | No per-key exposure/used-at chain available |
| Retained `agent_task_outcomes` rows | 0 | No task-outcome linkage available here |

The 16 non-tombstoned lexical matches were reviewed through bounded previews.
They concern tools such as `changes_digest`/lifecycle diagnostics, hashing,
mobile protocols or historical research decisions; the name match does not
establish digest-author provenance. No member was admitted as a bound digest
or an affected natural task. A generic decision or lesson can contain a
human-written summary without a `digest` name: that broader semantic population
was not exhaustively classified. The malformed tag row is a recorded inventory
limitation, not an authorization to repair live data.

The source-validity buckets **current / invalid / unknown are not applicable
to a zero typed-digest denominator**. In particular, 0 invalid digests here
must not be reported as a 100% valid corpus.

| Existing 30-day telemetry | Count | Interpretation |
| --- | ---: | --- |
| MCP `memory_get` calls | 179 | Query log agrees; 16 recorded misses |
| MCP `memory_search` calls | 20 | Query log: 18 FTS, 2 semantic; 2 FTS misses |
| MCP `session_bootstrap` calls | 3 | Tool invocation only; consumed rows not recorded here |
| Recorded errors for those calls | 0 | Tool success does not establish answer correctness |
| Exact-key gets of lexical digest candidates | 0 | Does not exclude search/bootstrap exposure |

These are retained telemetry counts, not guaranteed complete natural-use
counts. No traffic-class or source-byte evidence links them to a stale digest,
a natural task, a wrong action or owner rework. Missing exposure rows do not
establish that the collector was always disabled or that no exposure occurred.
No incident rate, task success rate, time saving or causal benefit is computed.

## Source-path finding, separate from live impact

Reviewed checkout HEAD: `9e2f22c53a9495c7ba9c9d7e24cb436cde4bf4c1`, with the
preceding uncommitted digest improvements present. File SHA-256 values are
recorded in private evidence so HEAD is not mistaken for those working bytes.

- [MemoryGetTool](../../crates/bridge/src/mcp_tools.rs) calls
  `current_digest_tool_result` / `digest_read::assess` only for kind `digest`.
- In the same file, `MemorySearchTool::execute` projects final hits through
  `memory_search_hit_value_with_continuity` or the compact projection; it does
  not call the digest assessment. Search may also write query, surfacing and
  coactivation telemetry.
- `SessionBootstrapTool::execute` selects scoped records and renders snippets
  through `format_bootstrap_memory_rows`; it does not call the digest assessment.
  Its surfacing writer is conditional and does not prove all displayed bytes
  were consumed by a task.

Thus the local implementation protects one exact-key entry, while other
entries do not enforce this source-binding check. This is static source
coverage evidence, not an observed exploit, harmful answer or production replay.
The repository source at the backend-reported build ref also lacks the new
assessment call; no runtime behavior or deployment claim is inferred from that
self-reported ref alone.

## Decision and reopening condition

Keep existing local code and tests. **Do not extend search/bootstrap, change
ranking, refresh legacy summaries, add bindings, enable collection, deploy a
binary or reopen sealed evaluations as a consequence of this audit.** Existing
R4/R4-A/R7 dispositions remain unchanged.

Reconsider one entry only when an ordinary task independently provides:

1. A specific retained digest/derived conclusion and the actual entry that
   returned or injected it.
2. Source state relevant to that time and the bytes actually returned; absent
   historical versions remain unknown rather than reconstructed from today's row.
3. An observable wrong action or extra verification/rework, with attributable
   owner cost or an independently checkable task postcondition.

Use existing task artifacts when that happens. There is no standing collection
campaign, new logger, recurring timer or requirement for the owner to fabricate
a sample. If a future task is affected by another store or generic decision
summary, identify that population explicitly before selecting a repair.

## Evidence and verification

Private local evidence directory:
`/Data/CascadeProjects/.analysis-reports/ab-digest-use-audit-20261025T120825Z/`.
No memory bodies are copied into this repository report. The one-off inspection
program is kept with the evidence, not installed as a product collector.

| File | SHA-256 |
| --- | --- |
| `inspect.py` | `de2affaf61dc1d7076dda70fa2b0b1a3de1efd440c98f6ca87c48c31c1d13024` |
| `evidence.json` | `cc6903b7b9f6a7c1cdaf0aedd82363eee9f14f7c7186bc94b8bc9d22dc179fb5` |
| `verification.json` | `469ec9948f6fe641f74c218b26175693ced01a81ceaf798b13d3d052360cc9f8` |
| `backend.json` | `4063615e302d9f0f69ada313c9c899aa13a6e3e07bf5338456bbebe7acb9c9fe` |

Verification: readonly extraction assertions and independent count checks;
artifact hashes; repository link checks; `git diff --check`. No product code
changed in this increment, so previous Rust/Python test counts are historical
and were not rerun or presented as this audit's validation.
