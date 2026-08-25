# R7 loss-tolerant Resident policy

Status: source, owner-local live canary, and installed-binary deployment PASS
on 2026-08-25.

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
- `ab-bridge` Resident tests: 38 passed after the final master rebase.
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

## Deployment closure

- Commit `925cf3fe61867c116fc4ab1602c45b233d48386f` was fast-forwarded to
  `origin/master`. The serialized master deployment path rebuilt that exact
  commit twice: first as a mutation-free dry run and then for installation.
  Both runs retained all nine deployed capability sentinels.
- The installed binary reports
  `agent-bridge 0.14.0 (v0.14.0-1866-g925cf3fe; 925cf3fe6186)` and hashes to
  `94ec3c7b6b84ab555e4096127f227427f1772e25a9d7973acc1699045509b3a9`.
  The independently installed wrapper is byte-identical to the repository
  template and hashes to
  `462d21056273aabe607683bd9c4fbe97be0a5d6401aab56d666ccbc0680e1e1a`.
- The installed wrapper's read-only `resident risk-preflight --json` returned
  `owner_loss_tolerant_profile_admitted=true`,
  `strict_profile_admitted=false`, `remaining_blockers=[]`, and confirmed
  that it neither started the provider nor read authentication nor wrote
  Resident state.
- Daemon, daemon-http, and Palace were restarted onto the installed inode.
  Every `/proc/<pid>/exe` hash matched the installed binary; both
  `http://127.0.0.1:7878/healthz` and
  `http://127.0.0.1:7979/healthz` returned `ok`.
- An online SQLite backup was created before deployment at
  `~/.local/share/agent-bridge/backups/state.db.pre-loss-tolerant-20260825T100942`;
  both that backup and the live database returned `PRAGMA quick_check=ok`.
  Binary, wrapper, audio-adapter, and runtime-asset rollback copies were also
  retained.
- Installed Doctor closed with zero failures and one expected owner-local
  sleeping-display warning. Session-scoped MCP clients still need their normal
  reconnect before they can adopt the new inode; this is not a Resident CLI or
  service deployment blocker.
