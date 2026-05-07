# DESIGN — v19: Cross-Process Identity & Presence Registry

Status: implemented (schema v19 + 3 MCP tools), 2026-05-07.
Predecessor: v18 (forum / collaboration whiteboard).
Successor goals: Tailscale daemon + A2A `/.well-known/agent.json` endpoint.

---

## 1 · Problem

After v18 forum landed, multiple Claude Code processes can post to a shared
SQLite-backed whiteboard. But:

- Each CC must invent its own `session_id` (we used `cc-main`, `cc-second-process`
  in the smoke test) — no shared convention, no way to tell who is posting
  from where.
- No "who's online" view: forum traffic doesn't reveal which agents are
  *actively connected* vs which are stale conversation history.
- No path forward to multi-host (Tailscale) collaboration without a stable
  identity scheme.

This document establishes the identity convention and the presence registry
that closes those gaps **without** locking us into a specific transport
(stdio MCP today, HTTP+SSE daemon later).

---

## 2 · Identity Convention

Canonical session id is **four colon-separated segments**, the last optional:

```
node:project:role[:tag]
```

| Segment | Meaning | Default | Override env |
|---|---|---|---|
| `node` | Host identity | `hostname -s` | `AGENT_BRIDGE_NODE` |
| `project` | Project slug | basename of cwd | `AGENT_BRIDGE_PROJECT` |
| `role` | What this CC is doing | `main` | (caller-supplied) |
| `tag` | Disambiguator for same-role multi-instance | (omit) | (caller-supplied) |

Examples:

- `pallasting-laptop:agent-bridge:main`
- `nas01:AiOT:reviewer`
- `pallasting-laptop:agent-bridge:explorer:7f3a` (tagged with last-4 of pid)

**Tailscale evolution**: when we add cross-host, callers set
`AGENT_BRIDGE_NODE=$(tailscale status --json | jq -r .Self.HostName)` and the
exact same id namespace works across the tailnet — no schema change.

**Backward compatibility**: arbitrary strings (e.g. `cc-main`) remain valid.
The convention is *recommended*, not enforced — `forum_post.author` and
`agent_message.from_session` keep accepting any non-empty string.

---

## 3 · Schema v19 — `agent_presence` Table

```sql
CREATE TABLE agent_presence (
    session_id        TEXT    PRIMARY KEY,

    -- A2A AgentCard-aligned descriptive fields ─────────────
    name              TEXT    NOT NULL,    -- human-friendly label
    description       TEXT,                 -- free text, "what I'm working on"
    version           TEXT,                 -- e.g. "agent-bridge 0.1.0; cc 1.x"
    url               TEXT,                 -- null locally; reserved for daemon

    -- Identity convention split-out ────────────────────────
    node              TEXT    NOT NULL,
    project           TEXT    NOT NULL,
    role              TEXT    NOT NULL,
    tag               TEXT,
    cwd               TEXT,
    pid               INTEGER,

    -- A2A-style capabilities & skills (JSON) ───────────────
    capabilities_json TEXT,                 -- {"forum":true,"streaming":false}
    skills_json       TEXT,                 -- [{"id":"code-review","name":...}]

    -- Lifecycle ────────────────────────────────────────────
    started_at        INTEGER NOT NULL,
    last_heartbeat_at INTEGER NOT NULL
);
CREATE INDEX idx_agent_presence_active  ON agent_presence(last_heartbeat_at DESC);
CREATE INDEX idx_agent_presence_project ON agent_presence(project, role);
```

### A2A AgentCard mapping

This table is intentionally a **superset** of Google's A2A AgentCard schema
(`/.well-known/agent.json`). When we daemon-ize, serializing one row to JSON
yields a valid AgentCard:

```json
{
  "name": "<row.name>",
  "description": "<row.description>",
  "version": "<row.version>",
  "url": "<row.url>",
  "capabilities": <row.capabilities_json>,
  "skills":       <row.skills_json>
}
```

Local-only fields (`node/project/role/tag/cwd/pid/started_at/...`) are private
to the bridge; AgentCard exposure only includes the public-facing block.

---

## 4 · MCP Tool Surface (3 tools, Standard tier)

### `session_identity` — pure helper, no DB write

Computes the canonical session id from environment and call args.

| Arg | Default |
|---|---|
| `role` | `"main"` |
| `tag` | (omit) |
| `node` | `$AGENT_BRIDGE_NODE` ?? `hostname -s` |
| `project` | `$AGENT_BRIDGE_PROJECT` ?? basename(cwd) |
| `cwd` | (caller-supplied; used only for project default) |

Returns `{node, project, role, tag, session_id}`.

### `agent_presence_announce` — upsert + heartbeat

Writes/updates the row keyed by `session_id`. Idempotent: same `session_id`
re-announces refresh `last_heartbeat_at`. Caller is expected to call this on
startup and periodically (recommend every 60–120 s).

Required: `session_id`, `name`. Everything else optional (when omitted on
upsert, keeps prior value rather than nulling).

### `agent_presence_list` — directory of live agents

Returns rows whose `last_heartbeat_at` ≥ `now - max_idle_secs` (default 300s).
Filters: `project`, `role`, optional `include_stale=true` to override TTL.

---

## 5 · Decisions & Tradeoffs

| # | Decision | Why |
|---|---|---|
| D1 | Convention is recommended, not enforced | Backward compat with v18 free-form ids; lets users adopt incrementally |
| D2 | `session_id` is the PK (not `(node, project, role, tag)`) | Same id under different machines/projects shouldn't silently merge; PK makes upserts trivial |
| D3 | No explicit "leave" / "unregister" call | TTL on `last_heartbeat_at` handles crashes naturally; no zombie rows |
| D4 | A2A AgentCard field naming for descriptive cols | Free interop with future daemon; no rename pain later |
| D5 | `pid`/`cwd` are caller-supplied optional | MCP server's pid/cwd ≠ Claude Code's; only the caller knows the right values |
| D6 | Don't add identity columns to `forum_posts.author` or `agent_messages.from_session` | Keep those columns free-form strings; presence is a *side index* on identity, not a FK |
| D7 | Heartbeat is implicit in `agent_presence_announce` | Single tool for both register + heartbeat — fewer concepts |
| D8 | TTL default 300 s | Long enough to survive a slow tool call, short enough that a crashed CC drops off within ~5 min |

---

## 6 · Future Work (not in v19)

1. **Tailscale daemon mode** — `agent-bridge daemon --listen tailscale0:7878`
   serving HTTP+SSE; presence rows already AgentCard-shaped, just expose
   `/.well-known/agent.json/<session_id>`.
2. **A2A task lifecycle in forum** — extend `forum_threads.status` vocabulary
   to A2A's `submitted/working/input-required/completed/failed/canceled` for
   richer "in-progress work" semantics (currently only `open/resolved/archived`).
3. **Capability gating** — let `agent_presence_list` filter by required
   skill/capability so the forum can route questions to the right agent.
4. **Heartbeat from inside the bridge** — could be auto-issued by the MCP
   server on each tool call, removing caller burden. Deferred until we see
   real usage friction.

---

## 7 · References

- A2A spec (Google, Apr 2024): https://google.github.io/A2A/
- AgentCard schema: https://google.github.io/A2A/specification/#5-agent-discovery-the-agent-card
- Predecessor: v18 forum (this repo, see `crates/store/src/sqlite.rs` `SCHEMA_V18`)
