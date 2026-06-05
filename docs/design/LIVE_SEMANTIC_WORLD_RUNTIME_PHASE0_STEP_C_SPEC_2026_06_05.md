# Live Semantic World Runtime — PHASE 0 Step C Spec (AB MCP `world.*` surface)

**2026-06-05 · author: Claude (`maxiaodeMac-Pro.local:agent-bridge:main`) · role: design + acceptance**
**Parent: Step B spec (this dir) · forum: thread #102 · dispatched to Codex**

## 0. Where we are

Step A (`bddae5b`, F1–F5 ACCEPTED #2431) + Step B (`10d58ee`, G1–G5 ACCEPTED #2443) proved the full PHASE0 thesis **inside onsen**: an out-of-process caller can patch the live world (director API) and perceive the **human's actual on-screen viewport** — pixel-grounded, render-grounded, with no-green-but-inert holding end-to-end — over a dev-flag localhost TCP host (`127.0.0.1:37691`, newline JSON).

What does NOT yet exist: an **agent** reaching that channel through agent-bridge. Today the host is only reachable by a hand-written TCP client. Step C makes it a first-class AB MCP surface.

## 1. Step C goal — one new capability

Expose the proven onsen live host as **agent-bridge MCP tools** so any agent (via AB MCP) can call `world.query` / `world.patch` / `world.visibility.query` against a live onsen session — with the **no-green-but-inert invariant preserved through the MCP layer**. AB is a **client** of the onsen TCP host; it does not embed Godot.

**Out of scope for Step C (→ Step D):** full `present()` (#92) auto-emission + #94 training-stream wire (Step C only makes the output *shape* present()-compatible); nexus second adapter; cross-node/remote host; branch/rollback.

## 2. Why this scope / why now

- The feasibility question is settled (A+B). Step C is **integration, not proof** — turn the validated channel into something an agent can actually use.
- It touches **AB core** (`crates/bridge` MCP tools) — a different magnitude than the onsen-contained A/B. Keep it minimal and additive: 3 thin client tools + honesty, nothing more.
- The honesty contract (no-green-but-inert) must be **re-proven at the MCP boundary** — a new layer is a new place for fake-green to leak in.

## 3. Contract

### 3.1 Three MCP tools (C1)
Add to `crates/bridge` (Tier::Niche — NOT in default/standard profile; exposed under `AGENT_BRIDGE_TOOL_PROFILE=all` or explicit allowlist, like the present/outcome tools):
- `world_query` — entity list + render-grounded bounds/visibility (maps to host query).
- `world_patch` — op/entity/args (move/rotate/flip/remove/place) against the live session.
- `world_visibility_query` — before/after pixel-grounded `screen_area` + `occluded` + `verified`.

Each tool is a **TCP client** of the onsen host: connect `127.0.0.1:<port>`, send one newline-JSON request (the Step B contract verbatim), read one newline-JSON response, return it. Endpoint config: tool param `host`/`port` > env (`ONSEN_LSWR_PORT`) > default `127.0.0.1:37691`. Set connect+read **timeout** (≈5 s; host's own capture timeout is 1200 ms).

### 3.2 Honesty preserved through MCP (C2) — the crux
The no-green-but-inert invariant must survive the new layer:
- host **unreachable** (no live session) → structured result `{verified:false, reason:"world_host_unreachable"}` — **never** a fake-success, **never** a panic/opaque error that reads as done.
- host returns `verified:false` (alpha-zero / not-in-shift / headless / capture_timeout) → AB surfaces `verified:false` **faithfully**, carrying the host's reason.
- malformed/locked response → `verified:false`, honest reason; no partial-truth.

### 3.3 present()-compatible output (C3, light)
The `world_visibility_query` result must carry a provenance/verify block shaped for #92 `present()`: `verify.method = "live_viewport_pixel_coverage"`, the render-grounded evidence (screen_area, flicker_frames, source), and `verified_to` semantics (only when `verified:true`). **No auto-`present()` emission and no #94 wire in Step C** — just make the shape ready so Step D can consume it without rework.

## 4. Acceptance — H-gate (I verify independently, refute-first)

I re-run against a live onsen host, **cross-checking the AB MCP tool's result against a direct TCP hit** to the same host (catch any AB-layer distortion).

- **H1 round-trip fidelity** — a `world_patch` move + `world_visibility_query` issued **through the AB MCP tool** returns a result matching a direct host hit (bbox move, pixel coverage, verified=true).
- **H2 honesty at the boundary** — (a) onsen host down → `world_host_unreachable`/`verified:false`, no panic; (b) alpha-zero via MCP → `verified:false`/`pixel_coverage_zero` faithfully surfaced.
- **H3 Tier::Niche** — absent from default + standard profiles; present under `profile=all`. (I check the profile gating directly.)
- **H4 present()-compat** — visibility result carries the verify/provenance block; `verified_to` honest (set only when verified).
- **H5 no AB regression** — `cargo test` green; build + deploy + `/mcp` reconnect clean; existing tools unaffected.

## 5. Task breakdown (Codex — CLAIM in #102 before starting)

- **C0** — decide + post for my sign-off BEFORE building: (i) exact tool names + param schema (align with AB tool conventions); (ii) endpoint config mechanism; (iii) the present()-compat provenance fields. One cheap round-trip (like SB0/T0).
- **C1** — the 3 TCP-client MCP tools, Tier::Niche.
- **C2** — honesty at the boundary (unreachable/timeout/false all → faithful not-verified).
- **C3** — present()-compatible output shape.
- **C4** — evidence: H1 (MCP vs direct-hit parity), H2 (host-down + alpha-zero via MCP), H3 (profile gating), H5 (cargo test + deploy). Post DONE + commit + evidence; I run the H-gate.

## 6. Boundaries

- AB is a **client**; the onsen host (Step B `10d58ee`) is unchanged. AB does not embed Godot.
- `world.*` tools honestly require a live dev onsen host; with none, they report `world_host_unreachable` (correct, not a bug).
- **Tier::Niche only** — never widen default/standard surface.
- **Work in an isolated worktree** for the `crates/bridge` change — `mcp_tools.rs` is hot + sibling-contended; avoid churn collisions (see repo lessons).
- No auto-`present()`, no #94 wire, no nexus, no cross-node — all Step D+.
- Implementation = Codex; design + H-gate acceptance = Claude. Independence preserved.
