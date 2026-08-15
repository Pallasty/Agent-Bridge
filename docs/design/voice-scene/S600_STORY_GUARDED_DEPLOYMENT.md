# S600 Story guarded deployment

The owner-authorized guarded deployment rebuilt from stable
`origin/master@f3ae34c0e15723b8d7a6cf12b2dbc969a2aaf5b4`. The post-build fetch
observed the same commit, and the anti-regression gate preserved all nine
markers found in the prior installed binary.

The installed `agent-bridge.real` is byte-identical to the release candidate:
SHA-256 `bde3918eb342cd42c61fb2932a01456e2f91cc0b9af99ea30b15f33b2931d133`,
size 76,406,104 bytes, and version source `f3ae34c0e157`. It contains the
`story_command_preflight` marker. The wrapper SHA stayed unchanged. The
repository and installed audio adapter are byte-identical.

The prior binary is recoverable at
`agent-bridge.real.bak-deploy-f3ae34c-20260801T071234`; its SHA matches the
pre-deployment baseline. The prior adapter is separately recoverable at
`audio_embody.py.bak-deploy-20260801T071235`.

A temporary stdio probe of the installed binary observed 108 tools with Story
hidden under `standard`, and 250 with Story visible under `all`. It did not
call the Story tool. All seven persistent MCP servers still reference the old
deleted inode, so deployment adoption is not yet a live-client claim. No MCP
was restarted, no client was refreshed, and no audio or memory path ran.
