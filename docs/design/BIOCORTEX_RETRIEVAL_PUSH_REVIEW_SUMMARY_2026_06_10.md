# BioCortex Retrieval Push Review Summary - 2026-06-10

Status: pushed and ready for review.

## Commits

Agent-Bridge:

- `6a8f027 Add BioCortex retrieval shadow boundary`
- Branch: `master`
- Remote: `origin/master`

BioCortex:

- `cde8c9a Add Agent-Bridge shadow adapters`
- Branch: `main`
- Remote: `origin/main`

## What Changed

Agent-Bridge now treats BioCortex as the active future integration direction
while keeping Seed as a disabled compatibility boundary.

The landed Agent-Bridge work adds:

- Review-only BioCortex shadow and retrieval side-signal surfaces.
- A feature-gated `biocortex-retrieval-shadow` CLI/MCP boundary.
- Retrieval gate fixtures for current, easy holdout, and hard holdout corpora.
- Alpha policy and runtime boundary documentation.
- A disabled Seed substrate shim so historical CLI/MCP surfaces fail cleanly.
- Optional Linux native avatar dependencies so no-default builds avoid Wayland
  system dependency failures.

The paired BioCortex work adds:

- `examples/ab_fixture_projection_shadow_adapter.rs`
- `examples/ab_retrieval_side_signal_adapter.rs`

Both adapters are read-only. They emit review evidence and do not mutate
Agent-Bridge memory, graph state, rewards, or runtime search ordering.

## Review Position

This batch intentionally does not make BioCortex part of the default runtime.
It creates a reviewable shadow boundary first.

Runtime mutation remains blocked by default:

- `runtime_adapter_approved=false`
- `default_search_order_changed=false`
- runtime execution requires the `biocortex-retrieval-shadow` feature
- runtime execution also requires `AB_BIOCORTEX_RETRIEVAL_SHADOW=1`
- `AB_BIOCORTEX_RETRIEVAL_DISABLE=1` is an operator kill switch

Seed is not deleted from the tree. It is moved out of the normal runtime path
so historical replay experiments remain possible without forcing default AB
builds to fetch or link the old Seed dependency.

## Validation

Pre-push validation:

- `git diff --cached --check` passed in Agent-Bridge.
- `git diff --cached --check` passed in BioCortex.
- `cargo check -p ab-bridge --no-default-features` passed.
- `cargo check -p ab-bridge --no-default-features --features biocortex-retrieval-shadow` passed.
- `cargo check --example ab_fixture_projection_shadow_adapter --example ab_retrieval_side_signal_adapter` passed in BioCortex.

Known remaining warnings were pre-existing:

- `ab-store` mixed-script warning for a beta-named test.
- `ab-bridge` visibility warning around `ToolPolicy`.
- `ab-bridge` dead-code warning for `resolve_audit_path`.

## Post-Push State

After push:

- Agent-Bridge `master` is aligned with `origin/master`.
- BioCortex `main` is aligned with `origin/main`.
- Agent-Bridge has only two intentionally excluded untracked environment
  scripts:
  - `scripts/format-data-f2fs-root-stage.sh`
  - `scripts/setup-sway-workstation.sh`
- BioCortex working tree is clean.

## Follow-Ups

- Decide whether to keep the two environment scripts, move them to a separate
  workstation setup branch, or delete them if they were one-off local notes.
- Add a narrow test for the CLI help surface if we want stronger coverage that
  `retrieval-shadow` only appears with the feature enabled.
- Keep BioCortex retrieval as review-only until a separate approval explicitly
  changes the runtime search contract.
