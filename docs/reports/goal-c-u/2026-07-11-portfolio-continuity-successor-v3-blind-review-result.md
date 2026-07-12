# Portfolio Continuity Successor V3 Blind Review Result

Date: 2026-07-11 PDT

Status: **TWO FIXED REVIEWS VALID / PROVENANCE AUDIT PASS / READY FOR SCORE
CLAIM DECISION / NOT UNBLINDED**. Both preregistered model reviewers completed
their single blind invocation. This report records execution provenance only;
it does not disclose review judgments, preferences, condition mappings, or
scores.

## Frozen Chain

```yaml
implementation_commit: 1d2da68181a276a71da36688f53c8f26f3770b50
contract_sha256: da9e190492d74824159bbff18eaeff02a4848921989f4077072f126e1d4e4bcc
capture_sha256: 35131cec096d5bb2bee481aee34c9fcc0f599431f5543cf791dec4f84f6da973
generation_sha256: 6b7de6a7ac1d32f35cc76117158d2e59765938bb3301e0eabaf83e22e1e0adc0
blind_packet_sha256: 50badd6c677963e0ba91cf7ad9e873c9ca8b2ff14c56d2d2ea08102b8b449f33
blind_map_sha256: 7fcfb4a793cf4677be35b9258a18ab489065daba948417a07a68f7be2cc9a04e
review_preflight_sha256: 6f8ae3911cca737b60727f2de1266a2594fcbae757bb3e12fd10eab7bb8c5c7a
fixed_review_count: 2
fixed_review_retry_count: 0
condition_label_leak_count: 0
score_claim_exists: false
score_output_exists: false
```

The deterministic requests were built from the exact blind packet by the
frozen harness. Each reviewer received only its fixed instruction, reviewer
slot, blind packet, and unpopulated output template. Neither command received
the generation packet, blind map, project files, memory, MCP, tools, web, or
condition labels.

## Claude Opus Slot

```yaml
reviewer_slot: reviewer_anthropic_opus
provider: anthropic
model: claude-opus-4-8
cli: claude 2.1.207
reasoning_effort: cli_default
reasoning_effort_pinned_in_command: false
request_sha256: 645500cd5bcaa65dd142c9773bfec97def454f2d49cd8977742dba8430415358
command_sha256: 57ce866ea046b8b0ea570c4bee57a160e320b5d53401f40257628c2ffecaad7c
raw_response_sha256: 028530c76aae07f88a3dff0b0be46d86c7b79bee642c09e59e271e4f8b4130d0
review_sha256: 028530c76aae07f88a3dff0b0be46d86c7b79bee642c09e59e271e4f8b4130d0
receipt_sha256: 7859b60edb62821b7bca0d417d43295202153a997c04a5307031dd8d1575aba6
session_id_sha256: 3c0d9295e8f3bcd967609b76ab823f4261fd59b43c827b4dd7dacd76711ab956
usage_sha256: 372d7f59d3cda941868ffeb8c9fcf2e45bcdb6c40936d505e56eab2331505e34
workspace_path_sha256: 33b2509bf430a1f9b588c3e7b6922e33bb5c91b82becf6c1df5e1b5c74b16b68
started_at_utc: 2026-07-11T12:37:03Z
completed_at_utc: 2026-07-11T12:49:34Z
duration_seconds: 751
response_bytes: 19599
case_count: 12
answer_review_count: 24
workspace_file_count: 0
stderr_bytes: 0
retry_count: 0
```

The exact frozen Claude command selected Opus 4.8 and intentionally omitted an
effort flag, so the receipt records CLI-default effort rather than claiming a
pinned level. Claude CLI usage also reported a 16-output-token internal Haiku
helper alongside the substantive Opus invocation. It made no web request and
did not alter the single command, zero-retry, byte-identical review result.

## Codex Sol Slot

```yaml
reviewer_slot: reviewer_openai_sol
provider: openai
model: gpt-5.6-sol
cli: codex-cli 0.144.1
reasoning_effort: max
reasoning_effort_pinned_in_command: true
request_sha256: eb812754847a8edef433baf39d3b689f6fdf4a59366dcdc4f7c7401ce5754cdd
command_sha256: f5c48ba0c2a23aa5af8b4a98e194f0ce36c11ab71c2ca673d2f29dee3a260c33
raw_response_sha256: 765019cad54c21ae2fda5b5c85adcf36f54745d4dd3cb08a5f88f22f36543e23
review_sha256: 765019cad54c21ae2fda5b5c85adcf36f54745d4dd3cb08a5f88f22f36543e23
receipt_sha256: 92533965cc1550639da4ad469b8e129297f814a4e36622facd17181480fe2c8d
session_id_sha256: 9d4619b401a068eb24a3ead901e97230ae79fc0079b9586ac9aa34077d9c3a1f
usage_sha256: df9ea9d4e48fe035bce5520295b398dc9db3b557c2e858425136e1bcf4d8a818
workspace_path_sha256: 0b49a142aac2acc9aef6708b96a97540820ec290e15c780a0bf51e7d686bb434
started_at_utc: 2026-07-11T12:51:46Z
completed_at_utc: 2026-07-11T13:02:51Z
duration_seconds: 665
response_bytes: 19525
input_tokens: 38120
cached_input_tokens: 8960
output_tokens: 27192
reasoning_output_tokens: 22272
case_count: 12
answer_review_count: 24
workspace_file_count: 0
retry_count: 0
```

The Codex event stream contained exactly one `thread.started`, `turn.started`,
`item.completed`, and `turn.completed` event and no tool event. It emitted one
143-byte model-catalog refresh timeout log line, but exited zero and returned a
complete valid review. Its temporary credential link was removed immediately
after the invocation.

The first post-invocation custodian packaging pass used the wrong local event
filename and stopped before creating a review or receipt. The frozen raw
response had already passed `validate_review`; the corrected packaging pass
used that same response and event stream. No model command was rerun, and the
invocation record remains `invocation_index=1`, `retry_count=0`.

## Joint Provenance Audit

The frozen validators rechecked both reviews and receipts from the blind packet
without opening the condition map for either reviewer. They confirmed:

- fixed reviewer-slot order and exact roster model/CLI identities;
- two distinct review, session, and empty-workspace hashes;
- complete 12-case and 24-answer coverage per reviewer;
- raw response and review bytes are identical in each slot;
- strict request and complete argv hashes match the frozen command profiles;
- no retry, tool event, MCP server, project context, workspace file, or
  condition-label leak;
- every private command, response, review, usage record, and receipt is mode
  `0600`;
- the score claim and score output do not exist.

An advisory Claude Sonnet gate call returned a zero-token session-limit 429 and
did not execute audit content. Its preserved response SHA-256 is
`d3541e8cc12655bc77d1040b595ff7197ee0571adf34992d30568c035bd5e4eb`.
A no-review-content Codex GPT-5.4/medium fallback then audited the same public
provenance summary in an empty read-only workspace with no tool events:

```yaml
request_sha256: 40a50b36b78c49cd0f4b165eace98920842b31bae175aeb15dce9bef4b324f08
raw_response_sha256: b6a85be73ee5dcdfeb6931e435d091b0e3453eff30870309ef0a84ffeda2cd33
normalized_decision_sha256: 014ca2ac1333215042aaaa87f9750edc41bd7d6910a773cff376314e1cc6791b
decision: PASS
next_gate: READY_FOR_SCORE_CLAIM_DECISION
blocker_count: 0
```

## Decision

The two-review gate advances to a separate **score-claim decision**. The next
phase must revalidate both reviews, receipts, commands, and raw responses in
the frozen slot order before the scorer atomically creates its deterministic
single-use claim. Only after that claim exists may the scorer open the
condition-labelled generation and map. Claim creation consumes the sole
unblinding allowance even if a later map or score validation fails.

This report does not authorize an implicit review retry, early map disclosure,
manual score edits, pooled-reviewer rescue, CI, release, versioning, tagging,
runtime promotion, retrieval-default changes, digest regeneration, or
write-side deployment.
