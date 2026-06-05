# ECC value adaptation for Agent-Bridge

**Source**: `affaan-m/ECC`, reviewed 2026-06-05.
**Status**: ACTIVE planning memo; first read-only readiness/validator slice
landed as `readiness_audit`.
**Board**: Agent-Bridge forum thread `#103`.
**Memory**:
`decision_ecc_value_ab_over_aiot_20260605`,
`todo_ab_ecc_adaptation_priority_20260605`.

## Decision

ECC has larger immediate value for Agent-Bridge than for AiOT.

Agent-Bridge already owns the same kind of surface ECC is trying to govern:
agent setup, hooks, tool profiles, skill intake, memory, terminal/worktree
coordination, and MCP observability. AiOT should benefit second-order by using
the improved AB surfaces as a dogfood consumer, rather than importing ECC
directly.

## Verified facts

### ECC

Reviewed shallow clone HEAD
`bc8e12bb80c904a5a9864797ef1fd1212aa82f3d`
(`feat: add dynamic workflow team orchestration surface`, committed
2026-06-04).

- Corpus shape: 251 skills, 63 agents, 79 commands, 12 legacy command shims.
- `npm ci` completed with 0 reported vulnerabilities.
- `node scripts/install-plan.js --profile minimal --target codex --json`
  produced a Codex-home dry-run install plan.
- `node scripts/install-plan.js --profile core --target claude --json`
  produced a Claude-home dry-run install plan.
- `npm run harness:audit -- --format json`: 80/80.
- `npm run observability:ready`: 21/21 Ready.
- `npm test`: 2621 passed, 0 failed.

### Agent-Bridge

Verified on 2026-06-05 against branch `feat/embodiment-grounding-v0`, HEAD
`33c9efaaebcc53fcfbcb864af4d30652e12690ea`, clean working tree.

- `crates/bridge/src/setup.rs` already has frontend/setup and toolset profile
  structure, including Codex, Claude Code, Codex CLI/IDE, Gemini CLI, Local CLI,
  Warp, Auggie, and Cursor surfaces.
- `crates/bridge/src/skills.rs` already indexes external skill repositories,
  parses metadata, lints risky skill content, and exposes routing/feedback
  surfaces.
- `README.md` already exposes audit/readiness-adjacent MCP tools such as
  `mcp_config_audit`, `mcp_dispatch_audit`, and `hook_status`.
- `docs/HOOKS-ENV.md` already concludes ECC-style
  `ECC_HOOK_PROFILE=minimal|standard|strict` has low marginal value because AB
  has richer per-hook env gates; the real gap was discoverability.
- `docs/design/ECC_INSTINCT_MINING_PROBE_2026_05_24.md` already closes the
  ECC error-mining idea as `NO_SIGNAL`; do not reopen that path without new
  source evidence.

## Non-goals

- Do not import ECC's 251 skills or 63 agents wholesale.
- Do not add hook profiles just to mirror ECC naming.
- Do not revive automatic error-resolution mining from Claude Code tool-error
  streams.
- Do not make direct AiOT architecture changes until AB has a dogfoodable
  surface.

## Borrowable mechanisms

| ECC mechanism | AB value | First AB shape |
|---|---|---|
| Shared source with target adapters | Keep Codex/Claude/Warp/Gemini behavior comparable without duplicating payloads | Audit existing setup adapters before changing install flow |
| Manifest install plan/apply/state | Make setup dry-runs and installed state inspectable | Compare AB setup output/state against ECC dry-run JSON before adding code |
| Harness and readiness scorecards | Give operators a one-glance answer for "is this surface usable?" | Add or extend a read-only readiness validator |
| Asset supply-chain validators | Reduce risk when routing third-party skills/prompts/agents | Extend existing skill lint/readiness reporting first |
| Guardrails around high-risk actions | Useful only when tied to real AB actions | Keep as opt-in follow-up after validator evidence |

## Priority

### P0 - Verification

Done for this review. The current state shows AB already covers several ECC
ideas, while the strongest gap is not "more hooks" but a consolidated,
source-backed readiness answer over setup, hooks, skills, tools, and adapter
assets.

### P1 - Planning artifact

This memo is the first landed artifact. Its job is to prevent future sessions
from re-researching ECC or reopening older null paths.

### P2 - Readiness/validator slice

First code-bearing slice landed in `crates/bridge/src/mcp_tools.rs` as the
read-only MCP tool `readiness_audit`. It returns JSON and does not change live
user config.

It reports:

- detected setup/tool profiles and their tool counts;
- readiness-adjacent tools present across all/standard/Codex/Gemini profiles;
- source-known hook coverage, with optional local install checks;
- source docs/tests/assets that anchor the ECC decision;
- closed ECC paths so old hook-profile and error-miner directions stay closed.

Acceptance gate: the output must distinguish "missing capability" from
"present but not validated" and must not require changing live user config.

### P3 - Setup plan-state hardening

Only after P2, compare AB setup plan/state with ECC's `install-plan` and
`install-state` behavior. Add plan-state detail only if the validator shows the
current setup flow is too opaque for operators.

### P4 - AiOT dogfood

Use AiOT as the first downstream consumer once AB has a stable readiness
surface. The AiOT value is strongest as operational validation of AB, not as a
separate ECC import.
