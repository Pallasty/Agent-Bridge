# Agno-inspired bounded result readback

Status: bounded offline validation complete; owner approved retaining the
manual utility and merging its source into public `main` on 2026-09-27.
Production integration remains unproven and is not enabled.

## Goal and authorization

Owner request: after the Agno review, plan validation and land feasible goals.
Follow-up authorization: retain the validated tool, merge and submit the code.
The accepted increment is one isolated offline readback prototype and a
reproducible comparison on fixed repository texts. It does not register an MCP
tool, capture live results, change storage or retrieval, or enable a runtime.

The mainline inspected is `6c4b1a9f332d8b9e9329f8d2914deed7db713453`.
Agno inspected revision: `8c3d8ec52b4a13c410fca97d07fbd507790cf29a`.

## Problem and value boundary

- Recent problem: this research session encountered truncated source/document
  tool responses requiring narrower reads; this is an assistant-tool observation,
  not a measured AB runtime defect.
- Thirty-day AB recurrence count: unknown.
- Owner time cost per occurrence: unmeasured.
- Smallest useful closure: an explicit, hash-bound existing UTF-8 file can be
  previewed, searched and completely reread with bounded responses.
- This increment: test those mechanics and count response bytes/calls on three
  pinned texts, with no model calls or production effects.
- Doing nothing: existing tail reads and manual source rereads remain available;
  no demonstrated production loss is attributed to this gap.

AB already has `agent_session_output` with tail reads and truncation metadata;
persisted stdout/stderr are capped at 64 KiB. `present.rs` has atomic HTML
artifact writes, but no matching general-purpose text pagination seam was
found in the bounded audit. Skill routing and toolset filtering already exist.
This prototype reuses ordinary files; it does not add a second artifact store.

## Preregistered inputs and comparisons

The manifest is `scripts/eval/fixtures/agno_readback_cases.json`. All three texts
come from the pinned Git revision: one existing verification JSON, one README,
and one Rust source file. Their hashes and six unique middle/end anchors were
chosen before running the prototype. The documents are inert bytes; historical
instructions in them do not establish current policy.

Compare these reference exposure policies:

1. One complete inline JSON text response.
2. One head-plus-tail response retaining 8,192 source bytes, split equally,
   plus an omission marker and JSON metadata.
3. One 1,024-byte preview, then a literal search and at most a 512-byte read
   for each of the two supplied anchors.

These are explicitly chosen reference policies, not an emulation of the current
AB transport or a randomized task benchmark. Exact queries are supplied by the
manifest, so finding them is an information-access check, not agent reasoning.
Count every candidate preview/search/read response, including JSON metadata.
Record request count as well as UTF-8 response bytes. Do not call bytes tokens.

Separately reconstruct each full artifact through 4,096-byte pages and compare
the entire SHA256. The exhaustive audit is not part of the selective exposure
policy; report its calls and bytes separately. Host timings are diagnostic only.

## Acceptance

- Only an existing regular UTF-8 file with the expected full SHA256 can be read.
- Full paginated reconstruction is byte-identical, including Chinese, emoji,
  long lines and end-of-file boundaries.
- Content respects the byte budget; metadata overhead is separately measured.
- Literal search states whether the search finished and where to continue.
- Missing files, changed bytes, invalid UTF-8, invalid offsets and unavailable
  content fail explicitly; no fabricated recoverable reference is returned.
- All six predetermined anchors are reachable on the pinned texts. Lower
  response bytes, if observed, must be accompanied by extra call counts.

The prototype starts from an already captured file. It neither tests nor
implements automatic capture, atomic offload publication, quotas, retention,
MCP client integration, multi-user authorization or crash recovery. Bytes lost
before capture cannot be restored. SHA256 binds bytes, not truth or authority.

## Decision rule

Retain the small offline utility if the mechanics pass. A failing result is
retained and corrected or rejected within this increment. Passing fixtures do
not authorize production adoption, broaden memory research, reopen R9/R10, or
establish task value. Reconsider integration only on a recurring natural task
with attributable evidence loss/cost and an existing useful capture seam.

## Primary references

- [Agno offloading example and storage-failure limits](https://docs.agno.com/examples/agents/result-offloading/offload-tool-results)
- [Pinned Agno read/search implementation](https://github.com/agno-agi/agno/blob/8c3d8ec52b4a13c410fca97d07fbd507790cf29a/libs/agno/agno/offload/tools.py)
- [Pinned Agno store implementation](https://github.com/agno-agi/agno/blob/8c3d8ec52b4a13c410fca97d07fbd507790cf29a/libs/agno/agno/offload/store.py)

The prototype is independently implemented with Python's standard library;
no Agno code or dependency is incorporated.

## Observed results

The machine-readable companion is
`2026-09-27-agno-result-readback-results.json`. Counts below include compact
JSON metadata, escaping and the final newline, following the utility's CLI
response format.

| Pinned text | Inline response bytes | Head/tail anchors | Selective response bytes | Selective anchors | Responses: inline / selective |
|---|---:|---:|---:|---:|---:|
| Historical verification JSON | 38,461 | 1/2 | 3,212 | 2/2 | 1 / 5 |
| README | 57,694 | 1/2 | 3,020 | 2/2 | 1 / 5 |
| Store source | 257,540 | 1/2 | 3,176 | 2/2 | 1 / 5 |

All six provided anchors were recovered. The three previews alone contained
none of them. These deliberately selected middle/end queries favor selective
reading; the 91.65%–98.77% response-byte reductions are conditional examples,
not expected production savings. Requests, tokenizer counts, model input
history/repeated context, disk overhead and network latency are not measured.
The evaluator holds verified bytes in memory; each real CLI invocation reads
and hashes the full file again, so these ratios do not imply lower disk I/O.

Full reconstruction was byte-identical for all three texts. It took 9, 14 and
62 pages and returned 39,955, 60,108 and 268,921 wire bytes respectively. Thus
reading the entire result through pages costs more response bytes than inline.
The unit suite also checks a small-input negative control where selective
reading costs more. The feature is useful only when the consumer needs a
bounded subset and can locate it.

### Verification performed

- TDD: the helper's 15 boundary tests failed before implementation; the
  comparison's 3 acceptance tests failed before its implementation.
- Independent review caught duplicate supplied anchors being counted twice;
  a failing regression reproduced it and distinct anchors are now required.
  The three fixed cases already had distinct anchors, so their metrics did not
  change.
- Combined focused suite: 19 tests pass, including UTF-8/emoji and long-line
  reconstruction, empty/EOF handling, search continuation, content budgets,
  malformed offsets, exact 8 MiB/oversize files, hash mismatch, invalid UTF-8,
  missing files, symlinks, directories, FIFOs and JSON CLI failure exits.
- Fixed-source comparison: exit 0, three complete hash-matching reconstructions
  and six reachable anchors, with `task_value_proven=false`.
- Actual CLI smoke: preview, literal search and a 256-byte read recovered the
  historical JSON's `"deployment": "not performed"` field in 1,964 response
  bytes across three calls. A fourth call after changing the file returned
  exit 2 with a SHA256 mismatch. The four-process local smoke took about
  574 ms; this is one host observation, not a task-latency benchmark.
- No Rust sources changed; no Cargo build or model/API invocation was needed.
  Ruff was unavailable in PATH; no Ruff result is claimed.

## Reproduce and use

From the repository checkout:

```bash
python3 -m unittest discover -s tests -p '*tool_result_readback.py' -v
python3 scripts/eval/eval_tool_result_readback.py
```

For an already saved text file, choose its expected SHA256 from its capture
record. The following uses the tracked JSON fixture and its preregistered hash:

```bash
python3 scripts/eval/tool_result_readback.py \
  --file docs/reports/main-rs-governance/2026-09-13-s18-verification.json \
  --sha256 bd3afdfe7a9dd7fe8b4a8caa8c3c95bc0607018fb4303df618d35afc7ebe1e05 \
  search --query '"deployment": "not performed"'
```

Use the returned `start` with `read --start <offset> --budget 512` while
retaining the same file and expected hash. Continue pages using `next_start`;
the offset and budget are UTF-8 bytes. A negative search is exhaustive only
when `search_complete=true`. Search returns non-overlapping literal matches.
The file limit is 8 MiB and the body budget is 4–16,000 bytes. JSON overhead is
additional. This POSIX owner-local tool does not establish an ACL or validate
the source's meaning, and a symlinked parent is not an authorization boundary.

### Retained decision

Keep the small, manually invoked utility and reproducible comparison. No
automatic output interception or new storage schema is justified by this
test. The next admissible integration decision needs a recurring natural
case, an existing pre-truncation capture seam and evidence that total task
cost or correctness improves. No new collection campaign is started.
