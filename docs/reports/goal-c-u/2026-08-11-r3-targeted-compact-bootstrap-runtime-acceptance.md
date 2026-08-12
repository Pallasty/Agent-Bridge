# R3 targeted compact bootstrap runtime acceptance

Date: 2026-08-11

## Integrated source

- PR: [#107](https://github.com/pallasting/Agent-Bridge/pull/107), merged.
- Authoritative source: GitHub `master` at `c6a924397f5f3817c59261c4b9d38efca973aed9`.
- GitLab `master` remained at `560fa90ec9e566b845f1e7d29cf44a4735d410dd` during this run; no dual-remote convergence is claimed.

## Build and install proof

- `scripts/deploy_from_master.sh --yes` ran with `AGENT_BRIDGE_DEPLOY_REMOTE=github` from a clean detached worktree.
- Built artifact: 61,287,344 bytes; version reported `agent-bridge 0.14.0 (v0.14.0-1472-gc6a92439; c6a924397f5f)`.
- Installed path: `/Users/pallasting/.local/bin/agent-bridge.real`.
- Installed SHA-256: `1967c6f6c06d9ca5615eef6e2b506a951936e1baadf46354fb1c6b75ca67b0b3`.
- Rollback binary: `/Users/pallasting/.local/bin/agent-bridge.real.bak-deploy-c6a9243-20260811T190115`.
- Rollback audio adapter: `/Users/pallasting/.local/share/ab-tts/audio_embody.py.bak-deploy-20260811T190115`.

## Runtime proof

- Restarted only the three launchd services: daemon-http PID 54296, daemon PID 54298, Palace PID 54302.
- `http://127.0.0.1:7878/healthz` returned `ok`.
- Palace root returned HTTP 200.
- Fresh MCP stdio consumer through the installed wrapper completed `initialize` and `session_bootstrap` successfully.
- Query: `targeted compact bootstrap runtime acceptance`; `frontend=warp`; `limit=8`.
- Response: 6,795 characters / 0.213 s; retained Git Currentness, Active Work, State digest, and Continuity Kernel; omitted unconditional Feedback, Perception, Distill, Activated, and Likely next-step panels.
- `agent-bridge doctor`: 5 ok / 4 warn / 0 fail. The remaining MCP warning is expected stale-client state: 13 stale `.real` consumers and no current `.real` consumer. No stale consumer was killed.

## Boundary

This accepts the merged compact-query behavior as installed and reachable through a fresh MCP process. It does not claim existing Warp/Codex MCP processes have reconnected; that remains a separate client refresh action.

## Evidence closeout

Later on 2026-08-11, before integrating this report:

- direct `ls-remote` checks showed GitLab and GitHub `master` aligned at `d803106b05da0def82e278e45926205c0332e748`;
- the installed artifact remained the accepted `c6a924397f5f` build with SHA-256 `1967c6f6c06d9ca5615eef6e2b506a951936e1baadf46354fb1c6b75ca67b0b3`;
- daemon health remained `ok` and Palace remained HTTP 200;
- `agent-bridge doctor` observed 9 current `.real` MCP consumers and only 2 stale Warp consumers, with 0 failures.

This follow-up closes the earlier dual-remote and Codex-client uncertainty. It does not claim the two remaining Warp consumers were refreshed.
