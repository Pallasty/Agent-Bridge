# A5-inspired memory visibility diagnostic

Verdict: **VISIBILITY_UNKNOWN**. Repeated rendered memory material exists in
the selected historical transcripts. Safe suppression is not established.
Goal 1 steps 1–3 are complete; the conditional filtering step is not admitted
by these findings. No runtime behavior was changed.

## Scope and authorization

Owner continuation on 2026-10-26: “很好！我们按照你的思路落地下一步目标。”
Executed the next step from
`../design/A5-INSPIRED-MEMORY-PLAN-2026-10-26.md`: inspect one existing foreground
consumer and at most three existing sessions, read-only. This did not open an
active collection campaign, run a hook, query the state database, call a model,
install A5, or change configuration. No CI or deployment was triggered.

AB source baseline: `2485fbad3535f51f85eedeb2fd22564205842994`.
Private local evidence packet:
`/Data/CascadeProjects/research/a5-visibility-diagnostic-20261026/`.
It includes frozen session bytes under `private/`, a bounded analysis script,
hashed per-delivery/per-row observations, route evidence and verification.
Private message bodies are not included in this repository report.

## Actual route differs from the repository implementation

The local Claude settings configure `UserPromptSubmit` to invoke
`~/.local/bin/ab-memory-hook`. The installed file is a v4 static SQL implementation,
SHA256 `1694d6ea174b4836fd4ed1a2756a5243024299cf90e7ecc2d7f6c4bec12e70b6`.
It reads 120-character memory snippets, selects up to 15 concept/handoff rows
and eight ranked rows, and emits `additionalContext`. Its turn counter defaults
to injection on turns 1, 9, 17, etc. Actual historical environment overrides
and exact historical hook bytes are unknown.

The checked-in hook is v5 and uses semantic `session_bootstrap` with a static
fallback. That source implementation is not proof of the installed path. The
selected transcripts contain native `hook_additional_context` attachments for
`UserPromptSubmit` with the static memory header, corroborating historical
static output, but not binding each event to today's installed-file hash.

The installed v4 code also contains an access-count update command; this
diagnostic did not run it, and whether that command succeeded historically is
unknown. Source/installation drift is a finding, not authorization to deploy
an update or a claim that an update would solve visibility.

## Bounded observations

Selection was the three most recently modified top-level JSONL files in the
local Claude Agent-Bridge project directory; no replacement sessions or
subagent histories were inspected. These are not a representative sample.
The observed client versions span 2.1.162–2.1.204. Different sessions contain
different subsets of those versions.

| Session prefix | Memory blocks | Repeated whole blocks after first occurrence | Rendered memory rows | Exact repeated rows after first occurrence | Compact boundaries |
| --- | ---: | ---: | ---: | ---: | ---: |
| `16e84869` | 1 | 0 | 23 | 0 | 0 |
| `7d31d4f1` | 38 | 12 | 874 | 817 | 24 |
| `bab3820b` | 1 | 0 | 23 | 0 | 0 |

Within the longer session, 468 repeated rows occurred in the same physical log
segment between recorded compact boundaries, totaling 155,171 UTF-8 bytes of
row text, excluding newlines. Another 349 repeats were first occurrences in a
later segment. These are repeated transcript bytes, **not token savings or
confirmed waste**. Physical log order does not prove active-branch membership
or retention in the next model request. A repeat after compaction can be useful.

The observations retain delivery UUID, parent UUID, timestamp, nearest recorded
prompt ID, log segment, workspace scope, hashed key and rendered bytes. The
prompt correlation is a log-order hint, not an authoritative request binding.
The output abbreviates project scopes as `[proj]` and truncates bodies: neither
exact record scope nor full source revision is recoverable from these snippets.
Identical snippets therefore do not prove identical complete memories.

## Why filtering is not justified yet

Some compact records carry preserved-message UUIDs. Across the 24 boundaries,
six attachment-ID membership occurrences match memory-block UUIDs. This is
limited preservation evidence at those boundaries, not an absence of lifecycle
evidence. It does not certify the complete material retained at each subsequent
request. The current hook does not consume those preservation records, an
authoritative context epoch, or a retained-material acknowledgment.

The existing hook execution log has 10,560 parseable records with only event,
timestamp, exit code and output size. It has no session ID or per-memory revision
and cannot establish a reliable session/delivery/retention join. Output size is
not a model-context receipt.

Thus the source-provenance and current-visibility prerequisites for suppression
are missing. Do not add a session-wide seen-key cache, suppress based on
`retrieval_surfacing`, or treat 155,171 repeated bytes as achievable savings.

## Verification and closure

All three frozen transcripts parsed without JSON errors. A separate pass checked
their SHA256 values, independently counted whole blocks/repeats, and checked
23 parsed rows per block. A second run of the analysis produced identical
observations. The evidence packet includes a SHA256 manifest. These checks
verify the diagnostic counts, not product behavior or memory usefulness.

Close this diagnostic with `VISIBILITY_UNKNOWN`; leave memory inclusion intact.
Revisit filtering only if the selected consumer supplies reliable current
retention/epoch evidence and full source identity for the demonstrated repeated
delivery. A read-only investigation of an existing host retention interface
could resolve that gap; installing a new observer merely to manufacture
evidence is outside this closure. Goals 2 and 3 remain conditional candidates.
