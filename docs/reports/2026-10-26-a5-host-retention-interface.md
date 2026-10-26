# Host retention interface assessment

Decision: **NO_SUPPORTED_RETENTION_RECEIPT_FOUND_ON_INSPECTED_ROUTE**.
The bounded interface investigation is complete. Keep `VISIBILITY_UNKNOWN`
for suppression decisions and leave ordinary memory injection unchanged.
This is a scoped negative result, not a claim that no host could expose such
an interface. Do not continue this lane by inventing another observation stage.

## Authority and inspected inputs

Owner continuation: “很好！我们按照你的思路落地下一步目标。” This follows
the [three-session diagnostic](2026-10-26-a5-memory-visibility-diagnostic.md)
and authorizes investigating existing host interfaces. No additional sessions
were selected. No product, hook or model was launched; no runtime settings,
state database, observer or collector were changed.

The local `claude` launcher resolves to the version-named ELF
`~/.local/share/claude/versions/2.1.220`, SHA256
`674f61f20ff306f3100cf9200e4c36c4b70278b5bef2884549819b942a89c863`.
The version label is from the installed path, not an executed version command.
It differs from versions observed in the earlier historical transcripts.

Official documentation was read on 2026-10-26. Its rolling content includes
features newer than this installed version; local embedded payload construction
and schemas were checked separately. Direct `.md` downloads returned HTTP 403;
the web tool successfully read the official pages. No complete documentation
snapshot is claimed.

## Interfaces and decision

| Surface | What the inspection establishes | What it does not establish |
| --- | --- | --- |
| Common hook input | Session, prompt and transcript identifiers | Actual retained material for the next request |
| UserPromptSubmit | A prompt-time entry and context output channel | Acknowledgment that earlier output is still retained |
| PostCompact | A completed compaction event and generated summary | Full retained-memory versions and a request-bound epoch |
| Status line | Context usage counts | Which specific memory bytes contributed to those counts |
| Transcript compact metadata | Historical preserved-message UUIDs | Synchronous current-request retention |

The [official hooks reference](https://code.claude.com/docs/en/hooks#common-input-fields)
documents prompt correlation and explicitly notes that transcript persistence
can lag in-memory conversation. Its UserPromptSubmit and PostCompact sections
describe prompt input and a post-compaction summary, respectively. Neither
documented payload enumerates the exact retained memories for a model request.
The [status-line reference](https://code.claude.com/docs/en/statusline#context-window-fields)
describes token usage from the latest response; these aggregate counts cannot
identify individual retained records. This last conclusion is our inference.

## Local implementation evidence

Static examination found the following readable implementation fragments in
the pinned ELF. Offsets are UTF-8/byte positions in that exact binary, not
stable symbols or public APIs:

- Around 259188589: common hook payload construction includes `session_id`,
  `transcript_path`, `cwd` and `prompt_id`.
- Around 259182146: UserPromptSubmit construction adds the prompt and title.
- Around 259170883: PostCompact construction adds trigger and compact summary.
- Around 260832766: compact metadata serialization includes preserved-message
  UUIDs. Internal restore code also consumes preserved-message metadata.
- Around 264011722: status usage construction emits aggregate token fields.

The exact matcher offsets and snippets are in `local-interface-check.json`.
This is stronger than merely finding feature-name strings, but remains static
inspection: it does not prove every path executes or certify an end-to-end
retention protocol. Missing strings named `context_epoch` or
`retained_message_ids` are not used as proof that no equivalent mechanism exists.

The two inspected configuration files have no PostCompact or status-line entry.
This is not a universal effective-configuration audit. Enabling those entries
would still not supply the missing receipt in the inspected payload contracts.
`prompt_id` could improve correlation, but correlation is not retention.

## Why transcript reconstruction is insufficient

Even accurate UUID reconstruction would need to account for branch selection,
in-memory changes not yet persisted, message transformations and the final
request assembly. The earlier static hook only exposes abbreviated scope and
120-character snippets, so exact memory-source revisions are independently
missing. A summary mentioning the same fact does not prove the original memory
bytes, constraints and exceptions survived.

Consequently, neither a PostCompact-driven counter, a file-tail parser, nor a
token-count heuristic can justify suppressing eligible content on this route.
No such adapter was implemented or installed.

## Closure and restart conditions

The research goal is complete; the conditional filtering feature remains
unimplemented. Reopen only on concrete new evidence: an existing supported host
surface that binds a current request/epoch to retained material identity, or an
explicitly changed goal that accepts a different, measurable tradeoff. Generic
continuation alone must not create another diagnostic stage.

Keep the installed-hook/source drift as a separate maintenance finding. Updating
v4 to v5 would not itself resolve the retention gap. Goals 2 and 3 retain their
original real-problem prerequisites; this negative result does not admit them.

Evidence directory: `/Data/CascadeProjects/research/a5-host-retention-20261026/`.
`check_local_interfaces.py` performs only static reads. Five targeted local
construction/schema markers were found, and the second run produced identical
JSON. Settings hashes match the prior diagnostic. Hash verification covers the
packet, not runtime behavior. No task-value or token-saving claim is made.
