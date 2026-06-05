# Live Semantic World Runtime — Phase 0 Spec (onsen seed)

> Status: SPEC / TASK PLAN, 2026-06-04.
>
> Implements: v0 RFC §15 (Phase 0 — Controlling Interpretation) in
> [LIVE_SEMANTIC_WORLD_RUNTIME_V0_2026_06_04.md](LIVE_SEMANTIC_WORLD_RUNTIME_V0_2026_06_04.md).
>
> Rationale: [LIVE_SEMANTIC_WORLD_RUNTIME_V0_REVIEW_2026_06_04.md](LIVE_SEMANTIC_WORLD_RUNTIME_V0_REVIEW_2026_06_04.md).
>
> Roles: design + acceptance = `maxiaodeMac-Pro.local:agent-bridge:main` (Claude);
> implementation = Codex (accepted in forum #102 #2380). This doc is both Codex's
> task plan and the verification rubric.
>
> Boundary: prototype/spike only. No core Agent-Bridge routing, no push without
> owner, no nexus adapter, no biocortex, no multi-AI authority, no branch/rollback
> UX, no 3D generation.

## 1. The one question Phase 0 answers

> Does the **patch → render → render-grounded perception → verify** loop close on
> onsen-hd **without screenshots as the AI's perception substrate**?

Concretely: an AI applies a semantic patch to the onsen world, then reads back
structured visibility (`screen_area` / `occluded` / readability) computed from the
**same render a human sees** — and a change that is invisible to the human is
provably reported as `not_verified`, never as success.

If this closes on onsen (already ~60% built: live patch API + single-source layout
+ real render), the general runtime is justified. If it cannot close here, a
greenfield runtime would not either. This is the cheapest honest proof.

## 2. Scope

**IN:** minimal `world-core` schema; minimal `design-api` (query / patch /
visibility); the onsen adapter spike; render-grounded visibility; one
`expected_effect` falsifier; acceptance F1–F5.

**OUT (explicit non-goals):** nexus adapter (the second seed — proves the schema is
not spatial-only — comes after onsen closes); biocortex-rs; multi-AI authority;
branch/rollback UX (deferred — query/patch/visibility only); 3D generation; a new
human client (reuse onsen's existing render/harness); committing to AB core.

## 3. `world-core` minimal schema (extracted, not invented)

The smallest subset of v0 §6 the onsen spike needs. Engine-agnostic JSON; the onsen
adapter maps it to onsen's concrete forms. Keep it minimal — nexus will stress it
later.

```text
World           { id, seed:"onsen", tick?, active_camera }
Entity          { id, kind, role, transform:{cell|position, orientation, footprint},
                  state:{occupancy,...}, tags[] }
Space           { id, grid:{dims, projection}, cameras:[{id,...}] }
Patch           { op, entity, args, reason, expected_effect:[clause], rollback_group? }
                  op ∈ move | rotate | flip | remove | place
expected_effect clause = { target, metric, to_op, to_value, from? }
                  e.g. { target:"arrival_landmark", metric:"screen_area", to_op:">=", to_value:0.25 }
VisibilityReport{ camera, entities:[{id, screen_area, occluded, readable?, role}],
                  warnings:[], verified: bool|null }
```

**onsen adapter mapping** (verified by the review's Explore pass and independently by
Codex in #2380 — `move_facility/rotate_facility/flip_facility/remove_facility` and
`request_render_refresh()` exist):

| world-core | onsen concrete |
|---|---|
| `World` | `GameLoopDirector` (+ `user://saves/slot_N.json` checkpoint) |
| `Entity` | facility (`GridProjection.FACILITY_CELLS` + `FacilityLayout` placements) |
| `Space` | `GridProjection` grid + isometric projection |
| `Patch.op` | `director.move_facility / rotate_facility / flip_facility / remove_facility / place_facility` |
| render / camera | the `SubViewport` used by `capture_unified_stage_operating_flip_v0.gd` |

> Codex: **confirm exact signatures against onsen HEAD before coding.** Do not trust
> the names above verbatim — onsen moves, and ground-truth-first beats a stale spec.

## 4. `design-api` minimal contract

Three calls (request/response JSON). `events.subscribe` and `branch/rollback` are
deferred.

```text
world.query(selector?)                  -> { world, entities[], spaces[] }
world.patch(patch)                      -> { applied:bool, before:{}, after:{}, render_refreshed:bool }
world.visibility.query({camera, entity_ids?}) -> VisibilityReport
```

**Hard rule (v0 §10 amendment):** `visibility.query` values MUST be derived from the
**same render pipeline the human sees** (the `SubViewport`/camera) — never from the
model dict / logical positions. If it cannot compute (no render available), it
returns `verified=false` / `occluded=null`, never a fabricated green value.

## 5. onsen adapter spike (what Codex builds)

The genuinely-new glue is the AB↔onsen transport. Take the thinnest viable path
first.

- **Step A — cheapest proof, reuses the existing harness.** An AB MCP tool invokes
  onsen **headless Godot** with `{patch?, visibility_query}` → onsen applies the
  patch via `director.*`, calls `request_render_refresh()`, renders the
  `SubViewport`, computes `screen_area`/`occluded` **from the rendered viewport**
  (camera projection + occlusion/coverage or rendered object-id buffer), and returns
  structured JSON. This mirrors `capture_unified_stage_operating_flip_v0.gd` but
  returns **data, not a PNG**.
- **Step B — human-in-loop, immediate follow-on.** The same `design-api` surface
  against a **live** onsen session (a small Godot TCP/WS server in GDScript) so a
  human plays while the AI patches and reads visibility. A proves the mechanics; B
  proves the human-in-loop. B is a separate task after A's acceptance.

**AB side:** new `Tier::Niche` MCP tools (`world_query` / `world_patch` /
`world_visibility_query`, names TBD) wrapping the transport. **No new core schema.**
**onsen side:** a headless entrypoint (Step A) / lightweight server (Step B) + the
render-grounded visibility computation.

## 6. Acceptance falsifiers (each MUST be able to fail)

The point of phase 0 is a loop that can honestly say "no." Every falsifier ships
with both a passing and a failing case.

- **F1 — patch is human-visible.** After `world.patch(move bath → cell X)`, the
  **rendered** `SubViewport` shows the bath at X (read **rendered** node/world
  positions, NOT the model dict).
- **F2 — visibility is render-grounded.** `visibility.query(entity)` returns
  `screen_area`/`occluded` from the actual camera render; moving/occluding the
  entity changes them correctly; when the render is unavailable it returns
  `verified=false` (honest), not a green default.
- **F3 — no green-but-inert** (the onsen lesson as a test). Construct
  model-says-moved-but-render-frozen → the system MUST report `not_verified` /
  surface the divergence, and MUST NOT report success. This proves the invariant has
  teeth.
- **F4 — expected_effect verification.** A patch with
  `expected_effect {arrival_landmark.screen_area >= 0.25}` is checked against the
  post-patch render → returns `verified | not_verified` honestly (and `not_verified`
  when the render/measurement can't confirm).
- **F5 — no screenshot perception.** The AI's perception input is the structured
  `VisibilityReport`, not a parsed PNG. Screenshots are allowed only as an audit
  artifact (per v0 §10).

## 7. Task breakdown for Codex (ordered, small)

- **T0** — confirm onsen integration points against HEAD (signatures, `SubViewport`
  harness, save format).
- **T1** — Step-A transport: headless Godot entrypoint taking `{patch?,
  visibility_query}` JSON → JSON.
- **T2** — render-grounded visibility computation in onsen (`screen_area` +
  `occluded` from the `SubViewport`/camera). **This is the crux — must be
  render-derived, not model-derived.**
- **T3** — wire `Patch.op` → `director.move/rotate/flip/remove/place` +
  `request_render_refresh()`.
- **T4** — AB MCP surface (`world_query` / `world_patch` / `world_visibility_query`)
  wrapping T1.
- **T5** — closed-loop dogfood: AI patch → visibility → `expected_effect` verify,
  plus the F1–F5 acceptance harness (each with a passing AND a failing case).
- *(Step B — live session server — is a separate follow-on after A's acceptance.)*

**Discipline:** cross-repo (onsen Godot + AB Rust). Keep the contract boundary at the
JSON `design-api`. Use an **isolated worktree** if touching shared checkouts (avoid
sibling churn). Post DONE + diff to #102; I verify before any merge.

## 8. Verification protocol (my gate)

Adversarial: each of F1–F5 is run by an independent skeptic defaulting to "refuted,"
and I read the **real render** (rendered positions / viewport), not the model. F3
specifically must demonstrate a real failure case (the system catching an inert
change). No empty-ACK — `verified_to`-style honesty (#92 discipline). Only after
F1–F5 hold do we discuss merge / owner sign-off / Step B.

## 9. Boundary (restated)

Prototype/spike only; stays inside v0 §15 phase-0. No AB-core routing; no push
without owner; no nexus / biocortex / multi-AI / branch-rollback / 3D-gen. The
`world-core` schema here is the minimal onsen-shaped cut; the nexus adapter (second
seed) will test and generalize it once the onsen loop closes.
