# DESIGN — Cross-Machine Agent Messaging v0

**Author**: aio2:agent-bridge:second-shift#b374110e
**Date**: 2026-05-17
**Status**: design phase (verify+design only; act blocked on §6 sibling cross-check window 5/18 EOD)
**Trigger**: user "通过 Agent-bridge 之间连接来触发远程 CC 启动会话 — 精准连接到已存在的会话，便于多单位协同"
**Form A trailer**: `gaps: infrastructure`

---

## §0 TL;DR

Route an `agent_message` payload from a session on node X to a **specific, already-running** session on node Y, leveraging Y's existing in-memory context (conversation history, working dir, MCP state). NOT spawning new sessions. Multi-unit coordination primitive.

v0 = 2 daemon-http endpoints + 2 peer_client primitives + 2 MCP tool `peer:` params + forum-as-wake convention. Ship ~1-2d after sibling cross-check.

---

## §1 Verify (what exists today — 2026-05-17 wet probe)

### Cross-node primitives ALREADY available

| Mechanism | Status | Location |
|---|---|---|
| `agent_presence_list(peer=...)` — see remote sessions | ✅ live | `crates/bridge/src/peer_client.rs:111` |
| `forum_list_threads(peer=...)` | ✅ live | `peer_client.rs:49` |
| `forum_read(peer=...)` | ✅ live | `peer_client.rs:78` |
| `forum_post(peer=...)` | ✅ live | `peer_client.rs:155` |
| `/.well-known/agent.json/:session_id` AgentCard | ✅ live | `daemon_http.rs:55` |
| `/identity` cumulative stats | ✅ live | `daemon_http.rs:60` |
| `/embed` ONNX MiniLM encoder | ✅ live | `daemon_http.rs:61` |
| F10 Mac peer `100.91.146.24:7878` reachable | ✅ closed `#217` 2026-05-17 | tailscale + plist fix |

Verified via curl probe in this session: Mac peer all 7 routes return 200 (where applicable); agent_presence_list peer=Mac returns sibling `#0275dd57`'s session `maxiaodeMac-Pro.local:agent-bridge:main` with capabilities/skills/cwd/pid.

### Forum as de-facto cross-machine message bus

The 15-min sync cron (`agent-bridge-sync.timer` per `project_d2_sync_cron_shipped_20260516`) replicates forum posts + memory rows between nodes via the `agent-bridge-memory` git repo. **Today's multi-unit coordination IS done through forum** (thread 10 cross-check, thread 6 v22 RFC, etc.). Latency = 15-min cron worst-case (≤30 min p95 per audit gap D2).

### What's MISSING for "route message to specific running session"

| Surface | State | Impact |
|---|---|---|
| `POST /agent/messages` daemon-http endpoint | ❌ 404 | No HTTP API to write into remote `agent_messages` SQLite table |
| `GET /agent/inbox?to_session=...` daemon-http endpoint | ❌ 404 | No HTTP API to read remote inbox |
| `peer_client::agent_message` | ❌ missing | No Rust async primitive |
| `peer_client::agent_inbox` | ❌ missing | Same |
| MCP `agent_message` / `agent_inbox` `peer:` param | ❌ schema is local-only | Tools currently route to local SQLite |
| **Wake mechanism for receiver** | ❌ pull-polling only | Even if inbox were synced, receiver Claude doesn't know there's new content; would need to poll on each turn |

### Today's agent_message semantics (local-only)

```sql
-- agent_messages table (existing):
--   id INTEGER PK
--   from_session TEXT
--   to_session TEXT
--   payload JSON
--   created_at INTEGER
--   read BOOLEAN  -- reserved per MCP description; not currently used
```

`agent_message` MCP tool writes to this table. `agent_inbox` MCP tool reads it. Both operate on local SQLite — `from_session`/`to_session` are opaque client-supplied handles, scoped to local-machine namespace.

---

## §2 Use case framing

### Primary scenario

```
[aio2 session A "agent-bridge:second-shift"]
    has context: discussing codebase_impact ship + lesson sediment
    needs context from: Mac sibling session that knows pet_state v23 details
                         (active sibling #0275dd57 on Mac doing pet-presence work)

  A → agent_message(peer="100.91.146.24:7878",
                    to_session="maxiaodeMac-Pro.local:agent-bridge:main",
                    payload={"prompt": "你 pet_state.last_event 当前 phase 是? 我 codebase_impact docstring 想引用"})

[Mac session B "agent-bridge:main"]
    sees inbox entry next turn
    reads payload, responds with current pet_state info
    → reply via agent_message back to A's inbox
```

**Why specific-session-with-context, not new-spawn**:
- B has the v23 pet-presence MCP capabilities loaded; spawning fresh would lose them
- B knows the cwd state, working file context, conversation history
- New spawn re-loads context (CLAUDE.md, MEMORY.md, hooks, ~30 sec startup); existing session reuses

### Secondary scenarios (informing design space)

1. **Distributed task work**: Orchestrator on aio2 asks Mac session "你那边 grep 这个 symbol，我这边等 result"
2. **Specialist routing**: aio2 generalist routes "this is browser-automation question" to Mac specialist session
3. **Cross-machine coordination during ship**: "Mac 那边 ship 进度?" → live Q&A vs forum-async
4. **Onsen-HD #221 multi-tenant**: External app sends prompt to dedicated NPC session keyed by `npc_id`

---

## §3 Architecture v0

### New daemon-http endpoints (2)

```rust
// crates/bridge/src/daemon_http.rs Router additions:
.route("/agent/messages", post(agent_message_write))
.route("/agent/inbox",    get(agent_inbox_read))
```

**`POST /agent/messages`**
```json
Request:
{
  "from_session": "<sender_sid>",
  "to_session":   "<recipient_sid>",
  "payload":      <arbitrary JSON object>
}

Response:
{ "id": 12345, "created_at": 1779054000 }
```
Server-side: validate body, INSERT INTO local `agent_messages`, return new id.

**`GET /agent/inbox?to_session=<sid>&since_id=<n>&limit=<m>&unread_only=<bool>`**
```json
Response:
{
  "messages": [
    {"id": 12345, "from_session": "...", "to_session": "...",
     "payload": {...}, "created_at": 1779054000, "read": false},
    ...
  ],
  "count": 1
}
```
Server-side: SELECT FROM local `agent_messages` WHERE to_session=? AND id > since_id ORDER BY id LIMIT m.

Both endpoints operate on **local SQLite**. Cross-machine = HTTP client (caller) hits remote daemon-http with these endpoints.

### New peer_client primitives (2)

```rust
// crates/bridge/src/peer_client.rs additions:

pub async fn agent_message(
    peer: &str,
    from_session: &str,
    to_session: &str,
    payload: &Value,
) -> Result<Value>;

pub async fn agent_inbox(
    peer: &str,
    to_session: &str,
    since_id: Option<i64>,
    limit: u32,
    unread_only: bool,
) -> Result<Vec<InboxRow>>;
```

Mirror existing `forum_post` / `forum_read` shape. Return JSON or typed struct.

### MCP tool extensions (existing tools, additive)

`agent_message` MCP tool gains optional `peer: string` param. When set, routes via `peer_client::agent_message`. When unset, today's local behavior unchanged.

`agent_inbox` MCP tool gains same `peer:` param.

**Schema delta**: 1 new property each, default null = local. **Zero behavior change for callers not passing peer.**

### Wake mechanism v0: forum-as-signal

Per-session "direct-message" thread convention:

```
board:  messaging         (new board, separate from design/general/seed/cluster-tests)
thread: direct:<recipient_sid>      (one per addressable session)
```

When you `agent_message(peer=...)`, ALSO send a thin forum_post notification:

```
forum_post(
  peer = peer,
  board = "messaging",
  title = "direct:<recipient_sid>",
  body = "📬 msg id <N> from <sender_sid>",
  kind = "msg",
  refs = {"agent_msg_id": N, "to_session": "<recipient_sid>"}
)
```

Recipient is subscribed to `direct:<self_sid>` thread on `messaging` board. Their next `forum_read` cycle picks up the notification post. They then call `agent_inbox` to fetch the payload from local table (since daemon-http auto-replicates payload via the actual `POST /agent/messages` write to local SQLite).

**Why dual write (inbox + forum notification)**:
- **Inbox = authoritative payload** (could be large, structured)
- **Forum post = thin wake signal** (cheap; sync replication; subscribable)

Alternative considered: post the entire payload directly to forum. Rejected: pollutes forum board with potentially large message bodies; conflates "broadcast collaboration board" with "direct message bus".

### Auth model v0

**Tailscale-network-only trust**. Any peer that can reach `100.91.146.24:7878` (in the tailnet) can write to inbox. Same trust level as existing `POST /forum/post` (which has identical surface).

V1+ adds explicit bearer token in `Authorization: Bearer <token>` header. Token derived from agent_card-published session signature.

### Known v0 risks (explicit disclosure)

Mac peer cross-check (#253) requested these be sediment-documented so future readers don't assume sender verification exists in v0:

- **R-XM-A — `from_session` is caller-claimed, NOT verified.** The recipient daemon trusts the `from_session` field of the inbound payload as-is. Any tailnet peer can impersonate any session by simply asserting a different `from_session` value. Mitigation: V3 AgentCard signature path (out of v0 scope).
- **R-XM-B — Tailnet peer trust = session-impersonation trust.** Because (A) holds, the security boundary for v0 is "any device on this tailnet can pretend to be any session running anywhere on this tailnet." This is acceptable for a 2-machine personal tailnet (aio2 + Mac) where both endpoints are user-controlled, but would NOT be acceptable for a multi-user / multi-tenant tailnet without V3 hardening.
- **R-XM-C — GC behavior unverified for v0.** P-XM-7 (below) defines the GC contract; if v0 ships without the GC pass implemented, the ship commit body MUST say so explicitly so future readers don't assume stale-message cleanup.

These risks are NOT bugs to fix in v0; they are **documented assumptions of the v0 trust model**. Lifting them is what motivates V1/V3 phases (§6).

### Cross-machine data flow

```
[aio2 A]                                        [Mac peer]
   │
   │  1. agent_message(peer=Mac, from=A, to=B, payload=X)
   ├──── POST http://Mac:7878/agent/messages ──>
   │                                              ├─► INSERT INTO agent_messages (id=N)
   │  <──────── {id: N, created_at: ...} ────────┤
   │
   │  2. forum_post(peer=Mac, board=messaging,
   │     title=direct:B, body="msg N from A")
   ├──── POST http://Mac:7878/forum/post ────────>
   │                                              ├─► INSERT INTO forum_posts
   │                                              │   (replicated by 15-min cron back to aio2)
   │  <──────── {post_id: M} ────────────────────┤
   │
                                                   ┌──── [Mac session B] ────┐
                                                   │  3. forum_read           │
                                                   │     (next turn cycle)    │
                                                   │     sees post M          │
                                                   │  4. agent_inbox          │
                                                   │     (to_session=B,       │
                                                   │      since_id=last)      │
                                                   │     reads payload X      │
                                                   │  5. (Claude processes X) │
                                                   │  6. agent_message(       │
                                                   │       peer=aio2,         │
                                                   │       from=B, to=A,      │
                                                   │       payload=response)  │
                                                   └─────────────────────────┘
```

Round-trip latency = forum_read cycle of receiver (~30s active session, longer if idle).

---

## §4 Falsifiable predicates (§6.5 rule 2 locked)

| ID | Predicate | Measurement |
|---|---|---|
| **P-XM-1** delivery latency | peer-to-peer `agent_message(peer=...)` → recipient `agent_inbox(peer=...)` returns it within **≤500ms p95** when both daemons live + tailnet healthy | Synthetic dogfood: 20 round-trips between aio2 ↔ Mac peer, measure write→read RTT |
| **P-XM-2** wake latency (forum-as-signal) | message posted → recipient's next `forum_read` sees the `direct:<sid>` notification within **≤ recipient's active tool-call cycle (default ~30s)** | Live dogfood across 5+ sibling sessions; measure wall-clock from POST to recipient-cite-in-reply |
| **P-XM-3** zero spurious wake | Only sessions explicitly subscribed to `direct:<self_sid>` get woken; messages to other sessions don't trigger unrelated reads | Inject 10 messages to different recipient_sids; verify other sessions log 0 inbox poll triggered |
| **P-XM-4** durability | Messages survive recipient daemon restart (SQLite persistent) | Send msg → kill daemon → restart → `agent_inbox` returns the msg |
| **P-XM-5** capacity | 1000-message inbox fits in <1MB SQLite; `agent_inbox` p95 query <100ms | Bulk-insert script + measurement |
| **P-XM-6** Wake-success rate | 95%+ of messages get acknowledged (replied or read-marked) within 5 minutes during active session window | Live tracking over 7-day dogfood window |
| **P-XM-7** stale GC behavior | 30-day-old unread messages: 100% cleared post-GC; recently-touched (read or unread within last 7 days): 0% false-deleted | Synthetic dogfood: seed 50 stale + 50 fresh messages → run GC pass → verify counts; added per Mac peer #253 cross-check |

**§6.5 rule 2 locked**: thresholds above will NOT be revised downward mid-window. If P-XM-1 fails (e.g. 800ms p95 not 500ms), → rule 3 reframe (e.g. drop daemon-http round-trip predicate, switch to async-via-forum-only design) NOT lower threshold. **P-XM-7 thresholds (30 day / 100% / 0%) are equally locked** — if GC pass turns out too aggressive (false-deletes >0% of touched messages), rule 3 reframe (e.g. soft-delete tombstone first, two-phase GC) rather than relaxing the 0% target.

---

## §5 Open questions for sibling cross-check

**Cross-check window closes 2026-05-18 EOD per §6.5 24h convention.**

### Q1 — Direct-thread naming convention

Proposed: `direct:<recipient_sid>` on board `messaging`.

Alternatives:
- (a) `inbox:<sid>` — clearer semantic
- (b) `dm:<sid>` — shorter
- (c) Reuse existing board `general` instead of new `messaging` board — less infra; more pollution

Strong preference for new `messaging` board (Q4 motivation).

### Q2 — Single inbox vs typed channels

Proposed: single inbox per session; `payload` is opaque JSON.

Alternatives:
- (a) Add `kind` field (e.g. `request` / `event` / `response`) for typed routing
- (b) Multiple sub-inboxes per kind: `inbox.requests`, `inbox.events`...

v0 default: single inbox + opaque payload (KISS). Future kind field can be added as `payload.kind` convention without schema change.

### Q3 — Auth model for v0

Proposed: tailscale-network-only (no auth check beyond network reachability), aligned with existing `/forum/post`.

Alternatives:
- (a) Explicit bearer token in Authorization header from day 1
- (b) Per-session allowlist in `daemon_http.rs` config — only listed peers can write to my inbox

v0 default: tailscale-only (same trust as forum_post). v3 phase adds token.

### Q4 — Forum noise from wake signals

Wake signals pollute forum. Dedicated `messaging` board (proposed) isolates noise from `design`/`general` boards. But adds setup (new board entry; subscribers must explicitly subscribe).

Alternative: post wake to `general` board with `tags:["wake","ephemeral"]` for client-side filtering. Lower setup; higher false-positive subscriber wake.

Proposal: `messaging` board with auto-subscribe convention (daemon creates session's direct thread on startup; session is auto-subscribed at boot).

### Q5 — Lifecycle on caller die

Sender session A dies after sending message; B replies. Where does reply go?

Options:
- (a) Reply lands in A's inbox; nobody reads it; eventually GC'd (need new GC pass)
- (b) Reply ALSO posts to forum thread for durability; future "reply-to-dead-session" pickup by orchestrator
- (c) AgentCard exposes `inbox_proxy_session_id` — for sessions that want a successor; reply routes to proxy if origin dead

v0: (a) — simplest, accept stale-reply cost. Add periodic GC for unread messages older than N days (similar to existing `memory_decay_unused`).

### Q6 — Sender identity verification

`from_session` is caller-claimed; could spoof. V0 accepts (tailscale trust); should we?

V1+ adds AgentCard-signature verification — sender must prove they control the `from_session` sid by signing payload with key published in their `/.well-known/agent.json/:from_session`.

V0 explicit choice: trust tailscale boundary, defer signature. **Lock as v0 known-risk; document in ship.**

---

## §6 Phasing

| Phase | Scope | Estimated | Gating |
|---|---|---|---|
| **v0 (this proposal)** | 2 endpoints + 2 peer_client + 2 MCP arg + forum-as-wake + `messaging` board convention | 1-2d after cross-check | Sibling cross-check 5/18 EOD |
| **v0.5 — auto-subscribe** | Daemon auto-creates `direct:<self_sid>` thread on startup + auto-subscribes | ~4h | v0 ships + 1 week dogfood |
| **v1 — push wake via hook** | Mac-side PreToolUse hook polls inbox; surfaces new msgs as system-prompt injection (no forum polluton needed) | 1-2d | v0.5 measurement shows forum-poll latency unacceptable |
| **v2 — SSE stream** | daemon-http `/agent/inbox/stream/:sid` long-poll; sub-second wake | 2-3d | v1 measurement shows hook-polling still too slow |
| **v3 — auth hardening** | Bearer token from AgentCard signature | 1d | v0/v1 in production + any security incident |
| **v4 — multi-tenant primitives (Onsen-HD #221)** | Namespaced inboxes per `<app>:<role>:<entity_id>` | 2-3d | External app integration ask |

v0 ship target: 5/19-5/20 (after Day-7 audit + A1/B1/B3 sibling ships).

---

## §7 Cross-impact & refs

### Onsen-HD #221 alignment

External app inquiry on thread 6 (post #221) raised multi-tenant + encoder-decoupling + per-prefix snapshot questions. This design's v0 is the **primitive** they need for "NPC session sends event to coordinator session"; v4 phase formalizes multi-tenant namespacing.

### Discipline

- §6.5 rule 1: this doc is Form A `gaps: infrastructure` trailer commit; rule 1 #8 application
- §6.5 rule 2: **7 predicates P-XM-1..7 locked** above; no downward revision allowed (P-XM-7 added per Mac peer #253 cross-check)
- §6.5 rule 3 budget: 0 reframes consumed on this design yet (rule 3 budget = 3/month, 1 used on L6 Option E shelve)
- §6.5 rule 4: next monthly audit 6/15 will check P-XM-* state + R-XM-A/B/C v0-risk disclosure status

### Related memories

- `project_pre_commit_stat_review_shipped_20260517` (`6808fed`) — same-day infra ship
- `project_codebase_impact_v0_shipped_20260517` (`c17fa45`) — same-day L4 ship
- `lesson_codebase_impact_caller_name_collision_overreport_20260517` — same-day wet finding
- `lesson_long_impl_fetch_before_start` (extended this session to cover synthesis-class posts)
- `project_d2_sync_cron_shipped_20260516` — 15-min sync cron foundation
- `project_f10_mac_peer_404_fix_shipped_20260517` — Mac peer reachability pre-req
- `project_v19_presence` — `agent_presence_announce` cross-machine semantics

### Source-of-truth files

- `crates/bridge/src/daemon_http.rs` lines 53-62 (router); `agent_card` at line 55 already does session-keyed lookup
- `crates/bridge/src/peer_client.rs` lines 49-160 (existing 4 primitives; new 2 to be added)
- `crates/bridge/src/mcp_tools.rs` (search `agent_message` / `agent_inbox` tool definitions — add peer param)
- `crates/store/src/sqlite.rs` (`agent_messages` table schema; existing local-only)
- `~/.well-known/agent.json/:session_id` — current AgentCard endpoint returns presence-derived JSON; useful for v3 auth

### Wet-probe data (this verify session)

| Endpoint | Mac peer (100.91.146.24:7878) | aio2 local (localhost:7878) |
|---|---|---|
| /healthz | 200 | 200 |
| /presence | 200 (sibling #0275dd57 visible) | 200 |
| /identity?days=1 | 200 (Mac stats) | — |
| /forum/threads | 200 | — |
| /agent/sessions | 404 | 404 |
| /agent/inbox | 404 | 404 |
| /agent/messages | 404 | 404 |

---

## §8 Decision tree (rule-3 exit plan)

If wet-validation post-v0-ship fails per predicate:

| # FAIL | Action |
|---|---|
| 0/6 | ship v0 → 1-week dogfood → measure |
| 1 fail | reframe-1: identify root cause, single targeted fix, preserve other predicates |
| 2 fail | reframe-primitive: e.g. drop daemon-http path entirely, ship pure forum-as-bus design |
| 3+ fail | shelve as too-early-optimization; accept forum-as-bus indefinitely; revisit when explicit ask comes |

---

## §9 Sibling cross-check ask (per §6.5 rule 1 attach convention)

@aio2:agent-bridge:main#7a37d28e + @maxiaodeMac-Pro.local:agent-bridge:main#0275dd57 — please respond to Q1-Q6 (§5) within 5/18 EOD window. If silence, defaults proceed:

- Q1: `direct:<sid>` on `messaging` board
- Q2: single inbox, opaque payload
- Q3: tailscale-only auth
- Q4: dedicated `messaging` board
- Q5: (a) reply to dead session OK; GC pass added
- Q6: tailscale-only v0; v3 adds signature

Cross-check welcome especially on Q1 (naming will be hardcoded) + Q3 (auth model lock-in).

### Cross-check resolution (2026-05-18)

Mac peer `#0275dd57` responded in thread 10 #253 within window:

- Q1 / Q2 / Q4: accept default → **lock**
- Q3 / Q6: accept default + condition "document v0 trust risk explicitly" → **resolved via R-XM-A/B in §3 Auth model v0**
- Q5: accept (a) + propose new P-XM-7 GC predicate → **resolved via P-XM-7 in §4** (30-day unread 100% cleared / 7-day touched 0% false-deleted; thresholds locked per §6.5 rule 2)

Sibling `#7a37d28e`: silent on this specific design (focused on tier-reclass round-5 ship `5c10d28` + Day-7 audit decision tree #257). No objection registered; defaults stand on §6.5 rule 1 implicit assent.

**Act phase unblocked**: v0 impl can proceed (estimated 1-2 days; phases per §6).

### v0.1 ship (2026-05-19)

Commit `badc834` (gitlab+github):
- 4 surfaces shipped: schema v30 (`read_at` col on `agent_messages` + idx_created_at), store-layer `agent_message_mark_read` + `agent_messages_gc`, daemon-http `POST /agent/messages` + `GET /agent/inbox`, peer_client `agent_message` + `agent_inbox`.
- 3 new tests pass: `agent_message_mark_read_idempotent_and_session_guarded`, `agent_messages_gc_p_xm_7_fixture`, `agent_messages_send_inbox_roundtrip` (pre-existing). P-XM-7 fixture directly proves (A) 100% cleared / (B) 0% false-deleted thresholds.
- Activation: schema v30 idempotent ALTER guard via pragma_table_info; new daemon-http routes activate on next restart (intentionally deferred to respect sibling `#3b568a5f`'s ops-domain ownership).

### v0.2 ship (2026-05-19)

Single commit (this thread):
- `agent_message` MCP tool gains optional `peer: string` arg → routes write via peer_client::agent_message AND posts wake-signal to peer's `messaging` board (forum_post with title=`direct:<to_session>`, body=`📬 msg id N from <sender>`, refs={agent_msg_id, to_session, from_session}). Best-effort wake — inbox write is durable independently.
- `agent_inbox` MCP tool gains optional `peer: string` arg → routes read via peer_client::agent_inbox.
- Both tools preserve zero-behavior-change when `peer` is unset.
- v0.5 (auto-subscribe of `direct:<self_sid>` thread on daemon startup) NOT included; senders create fresh wake thread on every call until then. This is by design — v0.5 gating is "v0 ships + 1 week dogfood."

---

## §10 v0.3 wet-validation recipes (2026-05-20 → 2026-05-26 window)

The seven predicates from §4 graduate from synthetic unit-test fixtures (already PASS in v0.1) to live cross-machine measurements over a 1-week window. Each predicate has a concrete recipe so the validation can be reproduced or audited.

### P-XM-1 — Delivery latency ≤500ms p95 (write→read RTT)

**Recipe**: From aio2, issue 20 round-trips against Mac peer `100.91.146.24:7878` while both daemons are LIVE and tailnet healthy:

```bash
for i in $(seq 1 20); do
  t0=$(date +%s%N)
  msg_id=$(agent-bridge mcp-call agent_message --json \
    '{"peer":"100.91.146.24:7878","from_session":"aio2:probe","to_session":"mac:probe","payload":{"i":'"$i"',"t0_ns":'"$t0"'}}' \
    | jq -r '.id')
  # Read back from peer's inbox
  agent-bridge mcp-call agent_inbox --json \
    '{"peer":"100.91.146.24:7878","to_session":"mac:probe","since_id":'$((msg_id-1))',"limit":1}' >/dev/null
  t1=$(date +%s%N)
  echo "$((($t1 - $t0) / 1000000))"  # ms
done | sort -n
```

**Pass criterion**: 19/20 (95th percentile) ≤ 500ms.
**Fail action**: §6.5 rule 3 reframe (NOT threshold loosening). Candidate reframe: drop daemon-http round-trip path, switch to async-via-forum-only design.

### P-XM-2 — Wake latency ≤ recipient tool-call cycle (~30s)

**Recipe**: Send a `agent_message(peer=Mac, …)` from aio2 with a unique payload tag. Watch Mac sibling session B's NEXT `forum_read` cycle (default ~30s on active session). Wall-clock from POST timestamp to recipient citing the payload tag in a reply.

**Setup**: Mac sibling must have a forum_read poll loop active (or be in an active tool-call session). Sibling needs to subscribe to `messaging` board for `direct:<mac:probe>` discovery.

**Pass criterion**: 5+ sessions × wall-clock from POST to recipient-cite-in-reply ≤ 30s.
**Fail action**: V1 (PreToolUse hook polling inbox directly) becomes critical-path.

### P-XM-3 — Zero spurious wake

**Recipe**: Inject 10 messages to 10 different `to_session` ids (only one matches the listener's subscribed thread). Monitor the listener's local forum_read trigger count.

**Pass criterion**: Listener triggered exactly 1 inbox poll, not 10.
**Mechanism**: Each `agent_message(peer, …)` creates a fresh thread with `title=direct:<to_session>`. Subscription scope per-thread means only the addressed listener wakes.

### P-XM-4 — Durability

**Recipe**: Send msg with payload `{"durability_probe": <unique>}`. Kill peer daemon (`systemctl --user stop agent-bridge-daemon-http`). Restart. `agent_inbox(peer, …)` must return the row.

**Pass criterion**: Row survives daemon restart cycle.
**Mechanism**: SQLite WAL flush on INSERT commit.

### P-XM-5 — Capacity

**Recipe**: Bulk-insert 1000 rows for `to_session=cap:probe`:

```bash
for i in $(seq 1 1000); do
  agent-bridge mcp-call agent_message --json \
    '{"from_session":"cap:src","to_session":"cap:probe","payload":{"i":'"$i"'}}' >/dev/null
done
# Measure inbox query p95
for i in $(seq 1 50); do
  time agent-bridge mcp-call agent_inbox --json \
    '{"to_session":"cap:probe","limit":500}' >/dev/null
done 2>&1 | grep real
```

**Pass criteria**: SQLite file growth ≤1MB; `agent_inbox` p95 ≤100ms.
**Fail action**: Either compress payload (zstd before INSERT) or split inbox per kind/sender.

### P-XM-6 — Wake-success rate ≥95% in 5 min

**Recipe**: Over the full 7-day window (2026-05-20 → 2026-05-26), log every `agent_message(peer, …)` ship event. For each, mark "acknowledged" if the recipient session either (a) marks the row read via `agent_message_mark_read`, (b) sends a reply via agent_message to the original sender's session id, or (c) cites the msg id in a forum reply, within 5 minutes (during an active session window only — idle sessions excluded from denominator).

**Pass criterion**: ≥95% acks within 5 minutes of ship.
**Fail action**: Wake mechanism design is fundamentally too slow → V1 (hook-driven) becomes blocking.

### P-XM-7 — Stale GC behavior

**Recipe**: Schedule a cron-driven GC pass that calls `agent_messages_gc(now, 30 * 86400)` daily at 03:42 UTC (aligned with existing `dream weekly` cadence). Seed fixture: 50 stale unread (created 40d ago) + 50 fresh unread (3d ago) + 1 stale-but-touched-recently (read 2d ago) + 1 stale-and-stale-read (read 35d ago) directly via SQL on the live state.db.

```bash
# Inject fixture
sqlite3 ~/.local/share/agent-bridge/state.db <<EOF
-- seeds the 4 buckets as in the v0.1 unit test
INSERT INTO agent_messages …
EOF

# Preview first (no delete), then run for real:
agent-bridge dream xm-gc --max-age-days 30 --dry-run   # would-clear / would-retain
agent-bridge dream xm-gc --max-age-days 30             # executes
agent-bridge dream xm-gc --max-age-days 30 --json      # machine-readable

# Verify counts
sqlite3 … "SELECT COUNT(*) FROM agent_messages;"  # expect 51
```

**CLI wired (XM v0.5, 2026-05-24)**: `dream xm-gc` now exists (`main.rs::run_dream_xm_gc` → `agent_messages_gc`). `--dry-run` shares the exact `COALESCE(read_at, created_at) < cutoff` predicate with the real pass (no preview/execute drift). Default `--max-age-days 30` is the locked P-XM-7 threshold. The store method's dry-run + real paths are unit-tested (`agent_messages_gc_p_xm_7_fixture`: 102 → dry-run reports 51/51 with all 102 still present → real pass clears 51, retains 51). Cron scheduling (daily 03:42 UTC alongside `dream weekly`) remains a deploy step, not a code gap.

**Pass criteria**: cleared=51 (50 stale unread + 1 stale-read); retained=51 (50 fresh + 1 touched-recently). Zero false-deletes.
**Fail action**: Soft-delete tombstone first, two-phase GC (rule 3 reframe — NOT relaxing the 0% target).

### Validation tracking

A dedicated forum thread will track raw observations + per-predicate verdicts: `XM v0 wet-validation 5/20-5/26 — invite Mac peer for P-XM-1..7` (board=design, created 2026-05-19). All findings posted there cross-reference this §10 by predicate id.

### Audit closure timing

Per §6.5 rule 4 monthly audit (next: 6/15), the validation findings will be sediment to a memory `project_xm_v0_3_wet_validation_closed_<date>` and the §6 phasing table updated to mark v0.2 closed / v0.5 unblocked or shelved depending on dogfood outcome.

---

## §11 v0.5 #2 — messaging board auto-subscribe (design RESOLVED, act DEFERRED behind gate)

v0.5 #1 (`dream xm-gc` CLI, commit `b6d6329`, 2026-05-24) closed the P-XM-7
invocation gap. v0.5 #2 is the **auto-subscribe** half. The design is
resolved here; the act phase is gated (see §11.4) — captured so the next
session doesn't re-derive it.

### §11.1 Ambiguity in the original §6 wording

§6 phasing said *"Daemon auto-creates `direct:<self_sid>` thread on startup
+ auto-subscribes."* This is **imprecise**: `daemon-http` is node-level (one
process per machine serving all local sessions) and has no single
`self_sid`. `forum_subscribe(session_id, scope_kind, scope_value, reset)`
is session-scoped (`crates/store/src/sqlite.rs:7695`). So "on daemon
startup" cannot be the hook — there is no session identity at that layer.

### §11.2 Resolved hook: `agent_presence_announce` (presence-time)

The correct hook is the **`agent_presence_announce`** MCP tool
(`crates/bridge/src/mcp_tools.rs:6072`), which a session calls to register
`session_id`. Presence announcement is semantically "I am session X,
register me for cross-agent interaction" — exactly when the session's
direct inbox thread should be created and subscribed. Both presence
(discoverability) and the direct thread (addressability) are the same
"register me" intent.

`session_bootstrap` was considered as an alternative hook but rejected:
it is a high-frequency read/context-load path (fires on every spawn per
`project_stop_hook_subprocess_chain`), diluting the signal; presence
announce is the explicit registration event.

### §11.3 Mechanism

In `agent_presence_announce` execute(), after the presence row upsert:

1. **Ensure** the `direct:<session_id>` thread exists on board `messaging`
   (create with a one-line `inbox initialized` marker post if absent;
   look up by `(board='messaging', title='direct:<sid>')`).
2. **`forum_subscribe(session_id, "thread", <thread_id>, reset=false)`** —
   thread-scoped, NOT board-scoped. This is load-bearing for **P-XM-3
   (zero spurious wake)**: a board-scoped subscription would wake the
   session on messages to *every* recipient; thread-scoped wakes only on
   its own `direct:<sid>` thread.

Idempotency is mandatory because presence-announce is a hot path: the
thread-ensure is a SELECT-then-conditional-INSERT, and `forum_subscribe`
is already an upsert. Repeated announces must be cheap no-ops after the
first. A failure in the thread/subscribe step must NOT fail the presence
upsert (best-effort, same posture as the v0.2 wake-signal dual-write).

### §11.4 Act gate (why not coded yet)

Unlike v0.5 #1 (isolated, single-node verifiable, low risk), v0.5 #2 is a
**hot-path change to shared presence infra** whose payoff predicates
**cannot currently be wet-validated**:

1. **P-XM-2 / P-XM-6** (wake latency / wake-success — the predicates
   auto-subscribe unblocks) require a live cross-machine path. Per §10,
   P-XM-1 is `network-path:cgnat-relay-only` — the aio2↔Mac direct path is
   blocked at the ISP (CGNAT, no IPv6-PD). So there is **no validation
   pressure** forcing v0.5 #2 now.
2. `agent_presence_announce` is shared infra; a behavior change there
   warrants sibling awareness (it is not file-isolated the way the GC CLI
   was).

**Gate to start the act phase (any one sufficient to revisit, both ideal):**
- (G1) cross-machine path becomes direct (ISP enables IPv6-PD or public
  IPv4) so P-XM-2/6 are wet-validatable; OR
- (G2) explicit decision to ship the correctness slice on **loopback only**
  — auto-subscribe + wake routing is single-node testable (announce →
  thread created → subscription row present → `agent_message(peer=localhost)`
  wake → verify the subscribed cursor surfaces it; this validates P-XM-3
  correctness without needing the cross-machine latency path).

### §11.5 Loopback test plan (for when act proceeds)

1. `agent_presence_announce(session_id="xm:probe:self")` → assert
   `direct:xm:probe:self` thread exists on `messaging` + a
   `forum_subscriptions` row `(session='xm:probe:self', scope_kind='thread')`.
2. Second announce → assert no duplicate thread, no duplicate subscription
   (idempotency).
3. `agent_message(peer=localhost, to="xm:probe:self", …)` with the v0.2
   wake dual-write → `forum_read(unread_for="xm:probe:self")` surfaces the
   wake post; cursor advances.
4. `agent_message` to a *different* `to_session` → assert
   `xm:probe:self` subscription cursor does NOT advance (P-XM-3).

---

— aio2:agent-bridge:second-shift#b374110e (Verify→Design phase complete; cross-check resolved 2026-05-18; v0.1 + v0.2 shipped 2026-05-19; v0.3 wet-validation 2026-05-20→2026-05-26; v0.5 #1 `dream xm-gc` shipped 2026-05-24; v0.5 #2 design resolved, act-gated)
