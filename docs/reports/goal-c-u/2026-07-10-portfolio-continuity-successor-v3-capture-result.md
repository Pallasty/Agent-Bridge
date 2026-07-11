# Portfolio Continuity Successor V3 Capture Result

Date: 2026-07-10 PDT

Status: **CAPTURE VALID / INDEPENDENT AUDIT PASS / READY FOR GENERATION
DECISION / GENERATION NOT EXECUTED**. The real v3 capture completed against a
read-only online backup of the live Agent-Bridge store. It did not call an
answer generator, create a generation-attempt claim, produce answers or a blind
map, start blind review, unblind, or score.

## Frozen Identity

```yaml
schema: agent_bridge.portfolio_continuity_answer_capture_redacted.v3
trial_id: portfolio_continuity_successor_v3_answer_20260710
implementation_commit: 1d2da68181a276a71da36688f53c8f26f3770b50
reviewed_prereg_binding: ec2df8b9f6db7d1a8e4a8308097960a54ddd1010
contract_sha256: da9e190492d74824159bbff18eaeff02a4848921989f4077072f126e1d4e4bcc
execution_repo_path_sha256: 116257ea10192e1be1c92ef77e005f06d597c006801ea9eefcb5a29d4fdcee74
spec_sha256: e3a7ce2bd0ec4f4ce06a483240e3942a16508824918d82b950c746c246427795
capture_sha256: 35131cec096d5bb2bee481aee34c9fcc0f599431f5543cf791dec4f84f6da973
redacted_capture_sha256: 39c15a69149e7ca28be715dab6e6ef7e7117bf43af9db9d35db5c6ef65b2de37
base_snapshot_sha256: ef8679fc81a2640a79db5553c2f7cc9a104d6ebbb12bdf8cb83ebfafc4f3b16f
runtime_source_commit: 1f75ede032b36db321c3e767d620eac5a6a44c6e
runtime_binary_sha256: 5ea3008c49bcc501e58f5cd6091b779350cb39b1b0105b3bce81b9439900ff7a
captured_at_utc: 2026-07-11T05:45:05Z
case_count: 12
condition_count: 2
isolated_run_count: 24
coverage_status: VALID
failed_case_count: 0
generation_claim_exists: false
generation_status: NOT_EXECUTED
```

The observed runtime identity was Agent-Bridge `0.14.0` at source commit
`1f75ede032b3`. The execution worktree was detached at the contract-bound
implementation commit. The private spec, raw capture, logs, and audit receipts
are mode `0600`; the frozen runtime copy is mode `0500`. They remain beneath
the canonical worktree's ignored `data/` directory.

## Coverage Result

All twelve cases passed the preregistered reference-coverage gate. Every case
returned ten unique `hybrid_retrieval` reference keys. The ten
non-abstention cases required at least two hits; the two abstention cases had a
minimum of zero. A retrieval hit on an abstention case does not decide whether
the answer should abstain.

The capture contains the complete 12-case by 2-condition matrix. The candidate
condition is the frozen portfolio digest; the reference is full hybrid
retrieval. Capture establishes only that the reference contexts are populated.
It does not establish answer quality, non-inferiority, or efficiency value.

## Deterministic Audit

The frozen v3 harness reloaded and revalidated the contract, private spec, and
raw capture. A separate deterministic audit then confirmed:

- the raw-capture hash equals the hash bound by the redacted packet;
- the redacted file and stdout packet are semantically identical;
- all 24 runs began from the same base snapshot and confirmed their isolated
  database paths;
- `source_db_opened_read_only=true`, `writes_live_ab_store=false`, and
  `calls_llm=false`;
- the redacted packet contains none of the exact prompt, retrieval-query,
  blind-seed, or digest-key values;
- capture stderr is empty and all private files have the required modes;
- no generation claim, generation output, blind packet, review, or score
  artifact exists.

The capture path opens the live SQLite source with `mode=ro`, takes one online
backup, and runs each retrieval against a temporary clone. MCP children set
`AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS=eval`, disable the outcome collector, and
receive only the isolated database path. Retrieval-side writes, if any, are
therefore confined to disposable snapshots rather than the live store.

## Independent Audit

An advisory Claude Sonnet capture audit ran in an empty workspace with safe
mode, no tools, no MCP, no project context, and no session persistence. It
received only the checked-in contract, redacted capture, frozen source
excerpts, and the deterministic audit summary. It did not receive the private
spec, raw capture, prompts, contexts, seed, digest key, answers, or blind map.
It is not either preregistered blind answer reviewer.

```yaml
cli: claude 2.1.207
substantive_model: claude-sonnet-4-6
request_sha256: 82fb34ec0b65d37dcaebeca674533eb8567f2021e2af0c0d95f2db8f6eed0ca7
raw_response_sha256: beced1062bc12ed7a9a303d39be7cb1dd173bb54fa64aa91998f6dff2e384e4f
decision: PASS
next_gate: READY_FOR_GENERATION_DECISION
blocker_count: 0
tools_used: false
web_requests: 0
```

The CLI response metadata also reported a 19-output-token internal Haiku helper
invocation. It made no tool or web request and is not used as an experiment
reviewer. The substantive Sonnet audit found no capture blocker and retained
the preregistered provider-overlap and scheduler-authorship disclosures as
residual experiment risks.

## Decision

The evidence supports advancing to a separate **generation-attempt decision**.
The next phase may consume attempt 1 only after rechecking the frozen worktree,
contract, runtime copy, capture hashes, output nonexistence, and attempt-claim
nonexistence immediately before invocation.

This report does not itself consume or authorize an implicit retry. It does not
authorize CI, release, versioning, tagging, runtime promotion, retrieval-default
changes, benchmark claims, digest regeneration, or write-side deployment.
