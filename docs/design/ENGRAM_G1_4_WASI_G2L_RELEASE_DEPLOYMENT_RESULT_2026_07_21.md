# Engram G1.4 WASI G2L — release deployment result

## Source and build

- source commit: `da556bc6988e08bb22d374282535a5a5df2d6dd2`;
- build mode: release, default production features plus
  `g14-wasi-component-runtime`;
- build target directory: `/Users/pallasting/.cache/agent-bridge-g2l-g2l-release`;
- pre-sign build SHA-256: `264e86f7fea601e2ca21efe190e167cd21b462b7bbbc48442f6845bb24bb235e`;
- size before deployment: 73,905,376 bytes.

## Deployment

The existing `scripts/deploy_from_master.sh` regression gate passed: every
capability marker present in the deployed binary was present in the new
binary. The previous binary was backed up at:

`/Users/pallasting/.local/bin/agent-bridge.real.bak-deploy-usebin-20260721T045521`

The new binary was copied to:

`/Users/pallasting/.local/bin/agent-bridge.real`

macOS ad-hoc signing and `codesign --verify` both passed. Signing changes the
file bytes, so the post-sign deployed SHA-256 is:

`818b2d46b92fb77833a09a4fa35cc9a7da22055f7d4ab4538b59be671ebce014`

## Live artifact check

The deployed binary's help exposes `g14-wasi-component`, and direct execution
against the accepted component returned:

```json
{"wall-epoch-seconds":946684800,"logical-nanoseconds":0,"quantum-nanoseconds":1000000}
```

Existing MCP processes started before this deployment retained the old mapped
inode. After the owner reconnected MCP, the active session reported
`git_sha=da556bc6988e` through capabilities; the fresh MCP process PID `52779`
started at `2026-07-21 05:53:19`. The deployed runtime feature is therefore
live in this session. Older MCP processes may still need their own reconnect.

Status:

**RELEASE BUILD PASS — DEPLOYMENT PASS — DIRECT LIVE-BINARY CHECK PASS — MCP LIVE VERIFIED**
