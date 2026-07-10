# Cross-machine memory sync

One-shot push of memories (and the edges between them) from this machine to
another over plain ssh + scp. No Tailscale required, no daemon, no schema
migrations on the remote — a fresh host gets a `state.db` populated in one
command.

## TL;DR

- Push `chat_session` memories from here to a peer:
- `./scripts/sync-handoff.sh user@host`
- If something looks off: re-run with `--dry-run` to see every step,
  or `--keep-temp` to leave the JSONL pair on both sides for inspection.

## When you would use this

- Move `chat_session` sediments / lessons / project notes from one host to
  another so you can keep reading them on the other side.
- Bring a brand-new linux or mac host into the agent-bridge mesh — once the
  wrapper installer (`scripts/wrapper/install.sh`) has put the binary in
  place, this script seeds its memory DB.
- One-off "I want last week's work on the laptop before I get on the
  plane" — pass `--since-ts <unix>` and you get just the recent slice.

This is **push-only** today. To get the peer's memories back here you run
the script in the other direction from over there. See
[What this doesn't do (yet)](#what-this-doesnt-do-yet).

## Quick start

```bash
# from the source host (the one whose memories you want to ship out)
cd /Data/CascadeProjects/agent-bridge
./scripts/sync-handoff.sh pallasting@192.168.1.99
```

What you should see (three steps, ~15s for a small slice):

```
→ step 1: local export — kind=chat_session loose_edges=true
{
  "edges_written": 9,
  "exported": 4,
  "memories_written": 4,
  "path": "/tmp/handoff-1778526462/mem.jsonl"
}
→ step 2: scp binary + exports to pallasting@192.168.1.99
→ step 3: remote import — XDG=/tmp/handoff-xdg-... profile=all embed=hash
{
  "edges_malformed": 0,
  "edges_skipped_dangling": 4,
  "edges_upserted": 5,
  "inserted": 4,
  "malformed": 0,
  "skipped": 0,
  "updated": 0
}
→ done.
```

The `edges_skipped_dangling: 4` line is not an error — see
[Glossary](#glossary-of-terms-youll-see-in-the-output).

## Flags

| Flag | Default | What it does |
|---|---|---|
| `<user@host>` | required | ssh target; must accept your key non-interactively |
| `--kind <K>` | `chat_session` | filter exported memories by `kind` |
| `--since-ts <N>` | none | only memories with `updated_at >= N` (unix seconds) |
| `--remote-binary <P>` | `/tmp/agent-bridge-handoff-<ts>` | where to drop the scp'd binary on the remote |
| `--remote-xdg <P>` | `/tmp/handoff-xdg-<ts>` | fresh `XDG_DATA_HOME` on remote so import doesn't touch a live DB |
| `--keep-temp` | off | don't `rm` the JSONL exports or remote temp files at exit |
| `--dry-run` | off | print every step without executing — also doubles as documentation |
| `--no-tools-profile` | off | skip `AGENT_BRIDGE_TOOL_PROFILE=all` on the remote (only if the remote binary already defaults to `all`) |
| `--remote-onnx` | off | don't force `AGENT_BRIDGE_EMBED_BACKEND=hash` on the remote (use ONNX instead — safe since the bg-init fix) |

The local binary path can be overridden with `AGENT_BRIDGE_BIN=...`; default
is `~/.local/bin/agent-bridge.real`.

## What's under the hood

The script is a 3-step pipeline (~189 lines, single bash file):

1. **Local export.** Spins up `agent-bridge mcp` over stdio on this machine
   and calls `memory_export` with `loose_edges=true`. Writes
   `mem.jsonl` + `edges.jsonl` into `/tmp/handoff-<ts>/`.
2. **scp.** Copies the local `agent-bridge.real` binary and the two JSONL
   files to the remote's `/tmp/`. (Copying the binary is the simplest way
   to guarantee the remote import understands the JSONL format — same
   binary on both sides, same schema.)
3. **Remote import.** Heredoc-builds an MCP request on the remote, pipes it
   into `agent-bridge mcp` with `XDG_DATA_HOME` pointed at a fresh dir,
   `AGENT_BRIDGE_TOOL_PROFILE=all`, and `AGENT_BRIDGE_EMBED_BACKEND=hash`.
   Parses the `id=2` response with python3 and prints the import report.

A `trap cleanup EXIT` removes the local tempdir plus the remote XDG dir,
binary, JSONL pair, and request file (unless `--keep-temp`).

The destination's import is **idempotent on retry**: re-running with the
same JSONL produces `inserted=0, updated=0` and re-evaluates dangling
edges. If the missing endpoints arrived between runs, the dangling
counter drops and `edges_upserted` rises accordingly.

## Glossary of terms you'll see in the output

### `loose_edges`

Two export modes for the edges file:

- **strict** (`loose_edges=false`, the default for `memory_export`): an
  edge is exported only if **both** endpoints are in the exported memory
  set. Guarantees the JSONL pair round-trips with zero dangling refs.
- **loose** (`loose_edges=true`, what this script uses): an edge is
  exported if **at least one** endpoint is in the set. This is the right
  default for narrow filters like `kind=chat_session`, because the
  `discussed_at` edges that connect a chat to its topic node have the
  topic on the *other* side of the kind filter.

Strict is still the right choice when you intend a full self-contained
slice (e.g. `kind=project` plus everything they link to, materialized
separately). The script picks loose because the prime mover for
cross-machine sync today is chat sessions.

### `edges_skipped_dangling`

Counts edges whose `from_key` or `to_key` doesn't yet exist on the
destination. **Not a failure.** Two cases:

1. The endpoint will arrive in a later sync — re-run the import after
   that sync and the edges link up automatically.
2. The endpoint will never arrive (was tombstoned, was scoped out by
   `--kind`, etc.) — the edges stay skipped indefinitely. They are not
   written to `memory_edges`, so the graph keeps its "no dangling refs"
   invariant.

Endpoint existence is checked inside the import transaction (so there's
no TOCTOU window), and the count is reported back per import call.

### `embedding_backend`

Each `memory_save` writes an embedding whose dimension matches the active
backend. The same model-aware rule applies when import creates or re-embeds a
row. Two local backends ship:

- **ONNX**: the compiled default is `gte-multilingual-base` at 768 dimensions.
  `all-minilm`, `e5-small`, and `para-ml` remain supported 384-dim selections
  through `AGENT_BRIDGE_ONNX_MODEL`.
- **hash** (FNV-1a hash projected to 384 dims): cheap, deterministic, no
  semantic signal. Used as a fallback while ONNX init is in-flight, or as
  a fast/offline mode.

The script forces `hash` on the remote because:

1. It's faster (no model load on cold start of a fresh host).
2. The sync workload doesn't *need* good embeddings — it just needs rows
   to land. You can `memory_reindex` later to upgrade embeddings if you
   want them in semantic search.

If you want real embeddings on the remote, pass `--remote-onnx`. Safe
since the [bg-init fix](#troubleshooting): ONNX init runs on a background
thread now, callers fall back to hash transparently while it loads.

## Troubleshooting

### "no MCP tool by name memory_export / memory_import"

You're running with the default `tools` profile, which hides Niche-tier
tools. The script sets `AGENT_BRIDGE_TOOL_PROFILE=all` on both sides by
default. If you disabled it with `--no-tools-profile`, restore it.

### `memory_import` hangs / no `id=2` response

Was the symptom of the original ONNX cold-start bug. Resolved at the
code layer in commit `04d6420` — fastembed init now runs on a background
thread, so `memory_import` never blocks on it. If you somehow hit this
on an old remote binary, work around it with
`AGENT_BRIDGE_EMBED_BACKEND=hash` (which is what the script does by
default).

### `edges_skipped_dangling: N` with N > 0

Read it as "N edges referred to keys that aren't on the dest yet."
Either:

- Run the sync again after the missing endpoints land — the import is
  idempotent and will link them up. The `edges_skipped_dangling` counter
  will drop and `edges_upserted` will rise.
- Accept it — for narrow filters this is the expected steady state.

### ssh key not set up

Standard fix:

```bash
ssh-copy-id pallasting@192.168.1.99
ssh -o BatchMode=yes pallasting@192.168.1.99 'echo ok'   # sanity check
```

The script uses `ssh -o BatchMode=yes` everywhere — if your key isn't
in `authorized_keys` it will fail fast rather than prompting.

### "export produced no file"

Local `agent-bridge.real` couldn't write to `$TMP_DIR/mem.jsonl`. Check
that `~/.local/bin/agent-bridge.real` exists (the wrapper installer at
`scripts/wrapper/install.sh` creates it) and that you can run
`agent-bridge mcp` interactively. `AGENT_BRIDGE_BIN=/path/to/bin
./scripts/sync-handoff.sh ...` lets you point at a non-default binary.

### Need to see what the script is doing without running it

```bash
./scripts/sync-handoff.sh user@host --dry-run
```

Prints every step as a `DRY: ...` line. The dry-run output is the
canonical operational reference — if this doc and `--dry-run` disagree,
trust `--dry-run`.

## Verified path

| Source | Dest | Transport | Result |
|---|---|---|---|
| aio2 (linux x86_64) | 192.168.1.99 (linux ubuntu, no tailscale) | direct LAN ssh | inserted=4, edges_upserted=5, edges_skipped_dangling=4 |

The 4 dangling edges were `discussed_at → vision_breathing_canvas`, which
isn't on the dest because we exported only `kind=chat_session`. Re-importing
after the topic node syncs across collapses the dangling counter to 0.

Cross-platform expectations:

- **Linux dest:** works as shipped (the verified path).
- **macOS dest:** works as long as the remote binary is a darwin build,
  re-installed via the wrapper installer (`scripts/wrapper/install.sh`).
  The script scp's the local binary by default, so a Linux source pushing
  to a Mac dest needs `--remote-binary /path/to/existing/darwin/bin` plus
  some flavor of "don't overwrite my binary." Easier: run the script
  *from* the Mac if both have one installed.

## What this doesn't do (yet)

- **Bidirectional sync.** This is push-only. To pull from peer to here,
  run the script from over there. A true peer-pull or rendezvous-style
  exchange isn't built.
- **Tailscale-aware fan-out.** No "push to all my tailnet peers" mode.
  v20a daemon-http exists but isn't wired into this script.
- **Scheduled / automatic syncs.** No cron, no systemd timer, no Stop-hook
  integration. Run it by hand when you want it. (The `agent-bridge sync`
  git-roundtrip path covers automatic memory-repo sync between hosts that
  share a forge — see [`context_two_node_workflow_pattern.md`][2n] in the
  auto-memory dir.)
- **Selective conflict resolution.** Imports use `conflict_policy=skip`,
  so a key that already exists on the dest is left alone. To overwrite,
  call `memory_import` directly with `conflict_policy=newer_wins`. (Not
  exposed as a script flag yet.)

[2n]: ../../../home/pallasting/.claude/projects/-Data-CascadeProjects-agent-bridge/memory/context_two_node_workflow_pattern.md
