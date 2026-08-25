# R7 loss-tolerant Resident policy

Status: source and owner-local live canary PASS on 2026-08-25; installed-binary
deployment is a separate claim.

## Owner decision

The current node has no Resident confidentiality requirement. The owner
accepts crashes, timeouts, resource exhaustion, orphan risk, replay, rollback,
and continuity loss when the outcome remains recoverable and does not cause
permanent system damage. Those risks remain recorded but no longer block live
M1 cognition.

The remaining fail-closed boundary denies irreversible host/data loss,
persistent system corruption, account/data mutation, public communication, or
other external action. One explicitly requested provider inference and its
bounded authentication, transport, and token use are expected, not an external
action grant.

The former seven strict requirements are now classified as:

| Requirement | Owner policy |
| --- | --- |
| positive empty model-tool manifest | mitigated for irreversible external writes; privacy/read-only exposure accepted |
| provider transport/tool-plane separation | strict privacy proof not required |
| credential-broker isolation | credential secrecy waived; minimal account-authority envelope retained |
| minimal mount/seccomp profile | mitigated by the outer read-only host-persistence envelope |
| complete process/cgroup custody | recoverable process loss accepted |
| pinned provider executable | required |
| subject-fenced cross-store transaction | recoverable half-commit/replay risk accepted for advisory-only M1 |

`strict_profile_admitted` remains false. The separate policy identifier is
`loss_tolerant_irreversible_damage_v0`.

## Implemented boundary

- The selected native Codex binary is copied once into a private per-run
  snapshot while SHA-256 is streamed; only an ELF snapshot matching
  `73dc5888888f411c1f0fa7b81d866e721dcc86b527ce8e3b2cf4708661e823ba`
  can execute.
- Production launch is fixed to root-owned, non-group/world-writable
  `/usr/bin/bwrap`. The original workspace is not mounted. The only writable
  host binding is the private temporary output directory; all other writable
  directories are isolated namespace storage.
- The provider home is ephemeral and receives only a read-only copy of
  `auth.json`. AB's shared service-credential notebook is bypassed for every
  `resident` wrapper command.
- User configuration and rules are ignored. Shell, unified execution,
  browser/computer, apps/plugins/MCP, goals, in-app updates/chat/dictation,
  guardian approval, dependency installation, elicitation, collaboration,
  steering, multi-agent, image generation, and web search are explicitly
  disabled.
- The existing deadline, process-group cleanup, output bounds, structured
  schema, wake/subject binding, event-stream audit, and receipts remain
  recovery and diagnostic controls.

The controls use supported Codex configuration surfaces documented in the
official [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
and [sandboxing guide](https://learn.chatgpt.com/docs/sandboxing).

## Verification

- `ab-agent` Resident provider tests: 11 passed.
- `ab-bridge` Resident tests: 33 passed.
- wrapper environment tests: 3 passed.
- Resident CLI parser test: 1 passed.
- Bubblewrap 0.11.1 started the pinned native Codex 0.149.1 under the production
  namespace/mount core and returned its version.
- Final debug-binary `resident risk-preflight`: owner profile admitted, strict
  profile not admitted, provider hash pinned, outer host persistence read-only,
  no external mutation authority, zero remaining blockers, and no preflight
  side effects.

One live canary used model `gpt-5.6-luna` at low effort and the inert event ID
`event:loss-tolerant-live-canary-20260825-01`. Wake
`wake-82016baae27d87e40f969d77a568d20a` completed in 22,688 ms with `no_op`,
zero provider tool events, one expected fail-closed code-mode diagnostic, a
matching expected/observed provider hash, an audited five-event JSONL stream,
and an observed provider-child exit. The result recorded
`owner_loss_tolerant_profile_admitted=true` and
`strict_profile_admitted=false`.

The canary journal used an isolated temporary state root. The initial command
used `AGENT_BRIDGE_DB` expecting an isolated SQLite database, but Resident's
general store path is selected by `default_db_path()` and therefore uses
`XDG_DATA_HOME`, not that command-specific environment variable. The canary
consequently appended one immutable verified `no_op` semantic event (row 3188)
to the normal store and recovered the prior compact digest; it did not delete
or rewrite existing history. `PRAGMA quick_check` returned `ok`. Future
isolated canaries must set `XDG_DATA_HOME` as well as
`AGENT_BRIDGE_STATE_DIR`.

## Remaining deployment procedure

The feature must be rebased onto the latest master, merged, and built by the
serialized master deployment path. Before installation, back up both
`agent-bridge.real` and the independently installed wrapper. After deployment,
verify the installed version/hash, repeat the read-only preflight through the
wrapper, check daemon/HTTP/Palace health, and reconnect each MCP client that
must load the new inode.
