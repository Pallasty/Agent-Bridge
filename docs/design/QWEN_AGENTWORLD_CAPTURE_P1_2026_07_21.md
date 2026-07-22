# Qwen-AgentWorld P1 — minimal real-pair capture

Date: 2026-07-21

Forum: Agent-Bridge design #186
Parent: `QWEN_AGENTWORLD_TRAJECTORY_P0_2026_07_21.md`

## Decision

P1 does not accept caller-supplied observations and does not capture arbitrary
terminal or shell traffic. Both would let self-asserted or secret-bearing text
masquerade as ground truth.

The first producer is therefore one fixed Bridge-owned read-only probe:
`workspace_summary`. Its action is a versioned constant and its observation is
limited to immediate file/directory/symlink/other counts. Names, paths, file
contents, prompts, commands, environment variables and transcripts are never
included in the observation.

## Gates

A capture requires all of:

- `AGENT_BRIDGE_AGENT_WORLD_CAPTURE=1` (default off);
- the Niche tool surface (`all` or `all-dev` profile);
- `per_call_opt_in=true`; and
- an actual Git worktree top-level confirmed by `git rev-parse`. `/`, the
  user's home directory, nested paths, fake `.git` markers and symlink roots
  are rejected. The filesystem device/inode identity (canonical path on
  non-Unix) is captured before enumeration and must match after Git revalidation.

The tool cannot execute caller commands or accept caller observations. It has
no network path, model integration, memory/canon write, attestation minting or
runtime-authority effect.

## Local evidence store

The public store writer accepts only a closed workspace-summary count type;
arbitrary probe kinds and action/observation JSON cannot enter through the
trait. `agent_world_capture` is an additive SQLite table intentionally absent from
sync/export paths. It retains at most 200 rows FIFO. Every row contains the
exact structured action and observation locally plus their SHA-256 digests,
the previous retained-chain hash and a row hash. Insert, chaining and pruning
occur in one SQLite transaction.

The MCP receipt and report use process-keyed commitments and never expose the
low-entropy action/observation digests. Both tools require the runtime feature
flag. Raw action/observation JSON remains inside the local database. A later
local resolver is a separate gate; this feature has no network egress path.

## Acceptance

`agent_world_capture_report` always loads and verifies the full retained ring;
its `limit` controls display only. It reports `acceptance_sample_ready` only when at
least 20 retained rows exist and the retained slice recomputes. This is local
consistency anchored at the oldest retained row, not external authenticity. The
20-row target validates capture mechanics, not model quality or generality.

Tests cover:

- default-off gate parsing and high-surface-only registry exposure;
- count-only observation privacy;
- transactional chaining and tamper detection;
- FIFO retention at 200 rows; and
- reconstructable local action/observation JSON with digest-only MCP output.

## Explicit non-goals

- no Qwen-AgentWorld model download or inference;
- no arbitrary Terminal/MCP transcript capture;
- no caller-supplied observation ingestion;
- no deployment, sync or external upload; and
- no claim that a process-local hash chain is cryptographic runtime attestation.

## Next gate

After this slice is reviewed and integrated, a live acceptance may enable the
flag temporarily and invoke the fixed probe 20 times. That deployment/reconnect
and live-write authority is separate from this source commit. Only after those
receipts pass should a P2 proposal consider one narrowly allowlisted real tool
adapter with secret scanning and an explicit local resolver.
