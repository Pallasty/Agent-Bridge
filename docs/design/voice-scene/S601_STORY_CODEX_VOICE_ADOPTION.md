# S601 Story codex-voice adoption

The `codex-voice` allowlist now adds exactly `story_command_preflight`; the
default and codex-essential allowlists remain unchanged. The change was driven
by a RED source-contract test and passed the repository pre-commit all-target
Rust check before commit `82fc5f169438`.

The guarded deployment rebuilt stable `origin/master@82fc5f16`, preserved all
nine installed feature markers, and installed a candidate with SHA-256
`5bd92a9d27629a16ef338ecbf4eb5e157ce1f86d8035f6a9c20d24cb52d921b5`.
The previous S600 binary is recoverable from
`agent-bridge.real.bak-deploy-82fc5f1-20260801T075628`.

An exact `codex-voice + essential` stdio probe against the newly installed
binary returned 103 tools instead of the prior 102 and included
`story_command_preflight`. It retained the same four named voice tools. The
probe did not call Story or any audio path.

All nine persistent MCP processes, including this Codex session, still hold an
older deleted inode. Installation and manifest eligibility are therefore
verified, but current-client adoption remains pending a Codex restart. This
stage does not restart clients, invoke Story, render audio, play audio, or write
memory.
