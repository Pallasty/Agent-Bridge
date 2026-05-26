# External Skill Intake Spike: OpenBMB MiniCPM5

Date: 2026-05-26
Status: validated, narrow indexer hardening implemented
Scope: Agent-Bridge external open-source skill indexing and optional local-worker evaluation

## Question

Can Agent-Bridge safely use OpenBMB/MiniCPM `minicpm5` as the first real
external open-source Skill source for the skills index, while keeping execution
gated and avoiding overlap with the AiOT MiniCPM5 tool-router spike?

## Verified Upstream Shape

OpenBMB/MiniCPM `minicpm5` publishes a `skills/` directory with top-level
router skills and backend-specific sub-skills.

The deployment router covers:

- `transformers`
- `vllm`
- `sglang`
- `llama-cpp`
- `ollama`
- `lmstudio`
- `mlx`
- `arclight`

The fine-tuning router covers:

- `trl`
- `llamafactory`
- `ms-swift`
- `unsloth`
- `xtuner`

The upstream README positions MiniCPM5-1B as a compact local/on-device model
for local assistants, coding agents, tool-use workflows, and reasoning
scenarios. It also documents MiniCPM5 XML-style tool calling and recommends
SGLang for OpenAI-compatible tool-call parsing.

The `minicpm5-deploy-mlx` skill is directly relevant to this Mac lane. It
documents:

- `mlx-lm>=0.31`
- optional `mlx_lm.server`
- first-run MLX JIT delay
- `<|im_end|>` as the extra EOS token for CLI/wrapper paths

The repository license is Apache-2.0, which is suitable for metadata indexing
with attribution.

## Current Agent-Bridge Fit

Agent-Bridge already has a `skills` CLI:

- `skills index <source>`
- `skills seed`
- `skills refresh`
- `skills discover`
- `skills search`
- `skills list`
- `skills show`
- `skills install`

The current indexer walks `SKILL.md`, `.claude/skills/**/*.md`, and
`skills/*.md`, parses frontmatter, runs heuristic safety lint, and saves each
skill as `kind=skill` memory.

This is close enough for a first MiniCPM5 intake, but the current source URL
path does not model branch pins as first-class provenance. For `minicpm5`, the
safe path is to clone the branch locally and index that local checkout, or add
branch/ref support before treating remote branch URLs as durable source
records.

## Validation Result

The first metadata-only intake used a local branch checkout:

- source: `https://github.com/OpenBMB/MiniCPM.git`
- branch: `minicpm5`
- commit: `44e6ae86fe8d7fbde2903beaeabccc3a45a8c19b`
- skill count: 15

`agent-bridge skills index /tmp/ab-minicpm5-skills-spike` indexed all 15
skills. Before indexing, `skills search MiniCPM5` had no matches. After
indexing, Apple Silicon / MLX queries surfaced `minicpm5-deploy-mlx`.

The validation also found that the existing source tags were too weak for local
checkout ingestion: records only carried `src:<temporary-directory-name>`.
That was enough for search, but not enough for safe external-source reuse.

## Implemented Hardening Slice

`crates/bridge/src/skills.rs` now adds git provenance tags when the indexed
source is a git checkout:

- `git_commit:<sha>`
- `git_branch:<branch>`
- `git_origin:<url>`
- `git_src:<owner>/<repo>`

It also adds operational risk tags in addition to the existing shell lint:

- `risk:pip_install`
- `risk:network_fetch`
- `risk:model_download`
- `risk:server_start`
- `risk:finetune_write`
- `risk:checkpoint_write`
- `risk:apple_mlx`
- `risk:gpu_required`

Follow-up hardening also teaches `skills index` to resolve branch tree URLs:

- `https://github.com/OpenBMB/MiniCPM/tree/minicpm5`
  clones `https://github.com/OpenBMB/MiniCPM.git` with
  `--branch minicpm5 --single-branch`.
- `https://gitlab.com/<owner>/<repo>/-/tree/<ref>` follows the same pattern
  for GitLab.
- Plain GitHub/GitLab URLs and SSH clone URLs continue to work.

The supported target is a repository branch/ref URL. Subdirectory tree URLs
whose branch name and path cannot be disambiguated from the URL alone remain
out of scope for v0.

`skills show --json` is the automation-facing review surface. It keeps the
existing human `skills show <key>` output unchanged, while exposing a
structured payload with:

- raw record fields: `key`, `kind`, `content`, `tags`, timestamps, scope,
  status, importance.
- parsed convenience fields: `source`, `path`, `lint`, `vendor`, `license`,
  `compatibility`, `tools`.
- grouped provenance: `git.commit`, `git.branch`, `git.origin`, `git.src`.
- operational risk values without the `risk:` prefix.

Re-indexed MiniCPM5 examples:

- `minicpm5-deploy-mlx`: `lint:clean`, `git_branch:minicpm5`,
  `git_commit:44e6ae86fe8d7fbde2903beaeabccc3a45a8c19b`,
  `risk:apple_mlx`, `risk:model_download`, `risk:network_fetch`,
  `risk:pip_install`, `risk:server_start`.
- `minicpm5-deploy-ollama`: `lint:warn:1` for `curl ... | sh`,
  plus model/network/install/server tags, without false `apple_mlx` or
  `gpu_required`.
- `minicpm5-deploy-vllm`: retains `risk:gpu_required`.

Verification passed:

- `cargo test -p ab-bridge skills -- --nocapture`
- `cargo check -p ab-bridge --all-targets`
- `git diff --check`
- `cargo build -p ab-bridge`

## Non-Overlap With AiOT Thread #40

Forum thread #40 already has an AiOT lane:

- T1 MiniCPM5 XML tool-call parser landed.
- AiOT is evaluating MiniCPM5 as an out-of-process local tool router.
- AiOT must avoid in-process Transformers because its pinned stack and Dream
  routes have their own dependency constraints.

Agent-Bridge should not duplicate that parser work. The Agent-Bridge lane is:

1. external Skill source intake,
2. safety/provenance metadata,
3. install/execute gating,
4. optional MLX worker boundary after indexing proves useful.

## Intake Policy v0

Index first, execute later.

External skills should enter Agent-Bridge in this order:

1. Source discovery
2. Source pinning
3. Static metadata extraction
4. Safety lint and risk tagging
5. Memory indexing
6. Search/show review
7. Explicit human approval before install
8. Explicit human approval before command execution

Recommended risk tags:

- `risk:read_only_doc`
- `risk:pip_install`
- `risk:model_download`
- `risk:server_start`
- `risk:network_fetch`
- `risk:checkpoint_write`
- `risk:finetune_write`
- `risk:gpu_required`
- `risk:apple_mlx`

The existing lint tags should remain, but they are not enough. A skill can be
lint-clean and still be operationally risky because it downloads models,
starts servers, writes checkpoints, or installs large Python stacks.

## MiniCPM5-Specific Assessment

Useful now:

- As the first external open-source Skill source for index/security/provenance
  validation.
- As a router-skill design example for Agent-Bridge's own skill
  recommendation surface.
- As a low-cost Apple MLX local-worker candidate.

Not useful now:

- As an automatically trusted executable skill bundle.
- As an in-process dependency inside Agent-Bridge.
- As a replacement for GPT-5.5/Codex on complex repository work.
- As a reason to build a fine-tuning path before routing/search value is
  proven.

## Validation Plan

Phase 0: read-only verification

- Confirm upstream branch, license, and skill layout.
- Confirm current Agent-Bridge index has no MiniCPM5 entries.
- Confirm local `agent-bridge skills` CLI can parse the branch checkout.
- Record findings in memory and forum thread #40.

Phase 1: metadata-only intake

- Index MiniCPM5 skills from a local `minicpm5` branch checkout.
- Inspect saved records with `skills list/search/show`.
- Verify lint/risk tags and source tags are good enough.
- Do not install any MiniCPM5 skill yet.

Status: done for the narrow MiniCPM5 sample.

Phase 2: index hardening if needed

- Add branch/ref/source commit metadata to indexed skill records if current
  source tags are ambiguous.
- Add operational risk tags beyond shell-lint warnings.
- Add `skills audit` or `skills show --json` only if manual review is clumsy.

Status: provenance tags, operational-risk tags, and branch-aware tree URL
source resolution are implemented. `skills show --json` is also implemented as
the first automation-facing review surface; broader `skills audit` remains a
possible future batch UX.

Phase 3: optional MLX worker spike

- Use `minicpm5-deploy-mlx` as a manually approved experiment.
- Prefer `mlx_lm.server` or a process boundary; do not embed MiniCPM5 into the
  Agent-Bridge daemon.
- Test low-risk tasks only: skill triage, log classification, memory candidate
  extraction, route suggestions.
- Measure latency, memory, and output quality against current GPT/Codex
  workflow before any persistent integration.

## Falsifiers

Stop or narrow the work if:

- The current indexer cannot preserve enough provenance for a branch-based
  source.
- Safety/risk tags cannot distinguish doc-only skills from install/server/
  fine-tune workflows.
- MiniCPM5 skill records do not improve search/recommendation behavior.
- MLX local worker setup is heavier than the tasks it would offload.
- The lane starts overlapping with AiOT's MiniCPM5 parser/router work.

## Immediate Next Step

Run `agent-bridge skills index https://github.com/OpenBMB/MiniCPM/tree/minicpm5`
directly, verify the resulting skill records match the local-checkout intake,
and keep MiniCPM5 skill execution/install gated behind explicit human approval.
