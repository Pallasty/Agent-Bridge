# ADR: CLI composition-root governance S14 rebaseline and continuous admission

## Status

Accepted on 2026-08-23.

- Decision scope: governance of `crates/bridge/src/main.rs`; this unit changes no
  Rust source, runtime behavior, deployment, or client process
- Audited source base: `6b041fbbdff5cd525cae4303fd50eeda086dad55`
- Source remote: `github/master`
- Remote state at audit: `origin/master` remained at
  `fd60af7d8cc125a6bc55d2dffa08581bec345164`, two commits behind the audited
  source base
- Predecessors: S0-S1 through S13, especially S7 Avatar inventory
- Next units: S14-B continuous gates, S15 daemon supervisors, S16 Avatar
  presentation seams, and S17 capability-interface evaluation
- Implementation posture: audit and decision only

## Context

S0 accepted `main.rs` as a CLI composition root rather than an arbitrary file
to split by size. S1-S13 then removed narrow, behavior-preserving vertical
slices while leaving process startup, dependency construction, cross-domain
dispatch, and effect custody visible at the root.

That direction worked. The accepted S0 base contained 21,700 lines. S13 reduced
the file to 18,246 lines, a reduction of 3,454 lines (15.9%). The current file
is still 2,002 lines smaller than the S0 base, but it has regrown to 19,698
lines. The regression is not evidence that the earlier architecture was wrong;
it shows that the finite extraction campaign did not install a continuous
admission rule for new composition-root code.

The current source also invalidates the earlier S14 planning snapshot at
`fd60af7d8cc1`. Two newer GitHub commits add `SpriteAssetAudit`, increasing the
Avatar command family from 47 to 48 variants and adding 96 net lines to
`main.rs`. This ADR therefore uses the fetched GitHub head, records the GitLab
lag explicitly, and does not claim dual-remote agreement.

## Reproducible baseline

Run these commands from a clean checkout at the audited source base:

```sh
git rev-parse HEAD
git rev-parse github/master
git rev-parse origin/master
wc -l -c crates/bridge/src/main.rs
git diff --numstat 924e7fdd3..HEAD -- crates/bridge/src/main.rs
rg -o 'AvatarOp::[A-Za-z0-9_]+' crates/bridge/src/main.rs | sort -u | wc -l
```

Observed results:

| Measure | S0 | S13 | Current |
| --- | ---: | ---: | ---: |
| `main.rs` lines | 21,700 | 18,246 | 19,698 |
| `main.rs` bytes | not recorded | not recorded | 785,546 |
| Change from S0 | baseline | -3,454 | -2,002 |
| Change from S13 | n/a | baseline | +1,452 net |
| `AvatarOp` variants | not separately frozen | 43 at S7; later growth | 48 |

The exact post-S13 `main.rs` diff is `+1453/-1`. The commits are:

| Commit | Net source purpose | `main.rs` delta |
| --- | --- | ---: |
| `6591a7496` | bounded Linux live loop | +378/-0 |
| `4d09e5ed9` | Qwen voice feedback | +311/-5 |
| `43007ccb1` | Linux live trial metrics | +84/-0 |
| `47d1a9d79` | production feature enablement | +1/-0 |
| `a5e4f7a26` | explicit Qwen LAN route | +11/-3 |
| `1e2bb8bc0` | voice observer | +228/-0 |
| `6988b17e0` | draggable projection | +7/-0 |
| `7c7c5d9ba` | focus-follow planner | +73/-0 |
| `0a59340bc` | focus-follow action executor | +285/-12 |
| `9f227a0af` | sprite atlas admission | +69/-1 |
| `6b041fbbd` | sprite readability metrics | +26/-0 |

All post-S13 growth is in Avatar-facing integration. This concentration, not
the absolute line count, is the reason to reopen governance.

## Current ownership map

The current physical regions are:

| Region | Current location | Physical span | Governance role |
| --- | ---: | ---: | --- |
| CLI schema and conversions | approximately `90-4465` | approximately 4,376 | public CLI contract |
| process entry and startup helpers | `4499-4784` | 286 | process boundary |
| `real_main` dispatch and mode startup | `4785-8721` | 3,937 | routing and runtime authority |
| Avatar schema | `847-2289` | 1,443 | 48 variants |
| Avatar early dispatch | `4994-6092` | 1,099 | 48 unique `AvatarOp` arms |
| Avatar executors and helpers | `8800-12927` | 4,128 | mixed projection and effects |
| BioCortex executor area | `12930-14568` | approximately 1,639 | mixed status and policy |
| Dream executor area | `14469-19040` | overlapping start, approximately 4,572 | reports and store workflows |
| Hub construction | `19042-19184` | 143 | dependency composition |

The regions are physical review surfaces, not owned-line counts. Helpers and
families overlap at some boundaries; line count must not be used as proof that
a whole region can move safely.

### Avatar delta since S7

S7 froze 43 schema variants, 43 dispatch arms, and their executor/effect map.
The five later variants are:

| Command | Character | Root-owned effects or inputs | S16 disposition |
| --- | --- | --- | --- |
| `FocusFollowPlan` | planning/reporting | reads Sway tree or supplied fixture | pure plan/result projection is eligible after characterization |
| `FocusFollowAction` | actuator | invokes bounded focus/window actions | keep acquisition, admission, ordering, and invocation at root |
| `LinuxLive` | long-running actuator | Sway/process/audio/network/retry and task lifecycle | keep effect custody at root; completed receipt formatting may move |
| `VoiceObserve` | observation with process boundary | invokes voice adapter and parses receipt | keep invocation and timeout/error ordering at root |
| `SpriteAssetAudit` | read-only admission | reads caller-selected image and controls exit status | renderer may move; path read and accepted/rejected exit contract stay explicit |

The command family therefore remains unsuitable for a wholesale
`cli::avatar` move. The newer read-only `SpriteAssetAudit` does not make the
older effectful family read-only.

## Decision

Retain the S0 composition-root direction and add continuous governance. Do not
replace it with a big-bang refactor.

### S14-B: continuous admission gate

Every change that adds or materially expands `main.rs` must classify each new
block as one of:

1. CLI schema or cross-domain routing;
2. process startup or dependency injection;
3. authority/effect adapter whose ordering must remain visible;
4. pure planning, projection, formatting, or aggregation logic.

Categories 1-3 may remain in the composition root when the change explains
why visibility is required. Category 4 must be placed in a binary-private or
library domain module unless a documented dependency or behavioral constraint
prevents it. A line-count budget is deliberately not imposed.

For every command-family change, acceptance evidence must cover the affected
contracts:

- clap command spelling, defaults, environment lookup, and help output;
- JSON and text output, including field presence and ordering where consumed;
- dry-run, preview, and confirmation behavior;
- validation and error ordering, exit status, stdout, and stderr;
- authority ownership and effect ordering;
- focused tests plus `cargo check -p ab-bridge --all-targets --quiet` for Rust
  movement;
- touched-file formatting and `git diff --check`.

Add ownership tests when a preregistered seam moves. The existing
`cli::workflow_feedback` ownership test is a precedent, not sufficient coverage
for other modules.

### S15: daemon-supervisor extraction

The first implementation target is the daemon arm inside `real_main`, not
`build_hub` and not an Avatar family move. Four background supervisors are
currently embedded directly in the branch:

- substrate coactivation tick;
- C3 self-check tick;
- retrieval-outcome application tick;
- orphan reaper tick.

Move each loop implementation behind a narrow domain-owned spawn function.
Keep the following visible in `real_main`: mode selection, explicit startup
order, the `Hub` resources passed to each supervisor, and the final `serve`
call. Preserve environment names, defaults, clamps, first-tick behavior,
missed-tick policy, log levels/messages where operationally consumed, and
store-absent behavior.

S15 must be split into independently reviewable units. It must not introduce a
generic scheduler abstraction unless two extracted supervisors demonstrate a
shared contract beyond both using `tokio::time::interval`.

### S16: Avatar new-growth control

Characterize the five post-S7 commands before movement. Extract only pure plan
construction, completed-result projection, and receipt formatting. Keep file,
Sway, process, audio, network, timeout, confirmation, retry, and Presence/store
custody at the composition/effect boundary.

S16 does not reopen all 43 S7 commands and does not create a monolithic
`cli::avatar` module.

### S17: capability-interface evaluation

Evaluate a dedicated Avatar live-execution capability only after S15 and S16
produce explicit, tested call boundaries. Proceed only if there is a second
consumer or a stable authority interface with deterministic parity evidence.
Otherwise retain the root-owned adapters.

## Preserved boundaries

The following stay in `main.rs` unless a later ADR demonstrates a stronger
contract:

- `main`, runtime construction, and top-level mode selection;
- cross-domain command dispatch;
- explicit authority consumption and effect ordering;
- shared dependency composition in `build_hub`;
- final daemon/MCP server startup.

`build_hub` is 143 lines of legitimate composition-root wiring. Its size is
not a current extraction trigger.

BioCortex and Dream are not reopened solely because their physical regions are
large. They require new churn, a second consumer, typed view boundaries,
deterministic parity evidence, or an explicit capability interface.

## Alternatives considered

### Replace the old plan with a whole-file split

Rejected. It would combine schema, startup authority, effects, and pure logic
in one mechanical review and would erase the behavioral evidence accumulated
by S1-S13.

### Continue feature delivery without governance

Rejected. The +1,452 net lines after S13 show that periodic extraction alone
does not prevent pure logic from returning to the composition root.

### Enforce a hard line-count ceiling

Rejected. Composition wiring and visible authority ordering can legitimately
grow, while a small pure helper can still be misplaced. Classification and
contract evidence are stronger controls than size.

### Move the complete Avatar family first

Rejected. S7's effect and authority findings remain valid, and the five newer
commands add more process, Sway, audio, network, path-read, and exit-status
contracts.

## Consequences

### Positive

- The successful S0-S13 direction remains intact.
- New growth receives a reviewable ownership classification.
- S15 reduces the largest startup-control block without hiding startup order.
- S16 can reduce Avatar presentation logic without transferring authority by
  accident.

### Negative

- `main.rs` remains large during incremental work.
- Characterization evidence must be maintained for each moved seam.
- Some mixed organization remains intentionally visible.

### Risks and mitigations

- **Remote drift:** fetch both remotes before implementation and record the
  exact source base; never infer equality from one remote.
- **Behavioral drift:** compare help, output, errors, and effect ordering before
  and after each extraction.
- **Authority laundering:** reject helpers that accept broad capabilities when
  only a completed immutable result is needed.
- **Generic abstraction too early:** require demonstrated shared contracts
  before introducing scheduler or capability frameworks.
- **Concurrent feature conflict:** perform structural work in clean isolated
  worktrees and coordinate changes to the red `main.rs` seam.

## Validation and rollback

This S14-A unit is valid when:

- its source SHA, remote divergence, line/byte count, post-S13 diff, and 48
  Avatar variants are reproducible;
- it changes documentation only;
- `git diff --check` passes;
- no build, test, deployment, or runtime acceptance is claimed.

Rollback is deletion or reversion of this ADR only. S0-S13 remain accepted.
Any S15-S17 implementation must have its own rollback boundary and validation
evidence.

## Related decisions

- `ADR-CLI-COMPOSITION-ROOT-GOVERNANCE-S0-S1-2026-07-28.md`
- `ADR-CLI-COMPOSITION-ROOT-GOVERNANCE-S7-AVATAR-INVENTORY-2026-08-01.md`
- `ADR-CLI-COMPOSITION-ROOT-GOVERNANCE-S8-AVATAR-BACKEND-PROBE-RENDERER-2026-08-02.md`
- `ADR-CLI-COMPOSITION-ROOT-GOVERNANCE-S13-SKILL-RETRO-AGGREGATOR-2026-08-02.md`
