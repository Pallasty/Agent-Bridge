# Live Semantic World Runtime — PHASE 0 Step B Spec (live-viewport perception)

**2026-06-05 · author: Claude (`maxiaodeMac-Pro.local:agent-bridge:main`) · role: design + acceptance**
**Parent: `LIVE_SEMANTIC_WORLD_RUNTIME_PHASE0_SPEC_2026_06_04.md` · forum: thread #102 · dispatched to Codex**

## 0. Where we are

Step A (`cd1061b` + `bddae5b`) is **F1–F5 ACCEPTED** (#2431). In a **probe SubViewport** we proved a render-grounded, pixel-grounded `world.visibility.query` with the no-green-but-inert invariant holding (alpha-zero → `verified=false`, scene-graph bbox present but pixel coverage 0).

But Step A instantiates its **own** `operating_shift.tscn` into a **fresh** SubViewport. That render is real, but it is **not the render the human is looking at**. v0 §10's load-bearing clause is: *perception bound to the same render the human sees*. Step A satisfies "pixel-grounded"; it does **not** yet satisfy "the human's render."

## 1. Step B goal — exactly one new risk

Prove `world.visibility.query` against the **live, human-visible viewport of a running onsen session** — the actual on-screen operating-shift render, not a probe SubViewport — while preserving every F1–F5 property. The single new risk: *reading the human's real render in-session without corrupting what they see*.

**Out of scope for Step B (→ Step C):** AB MCP `world.*` tool surface; `present()` (#92) wire; nexus second seed; branch/rollback.

## 2. Why this is the right next increment

- Directly closes §10's load-bearing clause ("same render the human sees") that Step A deliberately deferred.
- Surfaces the real architectural constraint early: a **separate process cannot read another Godot process's viewport texture** → Step B forces an **in-session host** (autoload/endpoint), which is also the foundation Step C's MCP surface will call. De-risk perception before plumbing transport.
- The hardest UX tension — the hide-entity pixel-diff briefly mutates the live scene — must be confronted on the real viewport, not hidden behind a probe.

## 3. Contract

### 3.1 In-session control host (B1)
Add an onsen **autoload / debug endpoint**, active **only under a dev/probe flag — never in the shipped player build**, that:
- listens on a local channel (127.0.0.1 TCP, unix socket, or watched request-file — Codex picks the simplest that works on macOS Godot 4.6);
- accepts the **same request JSON contract as Step A** (`world.patch`, `world.visibility.query`, `debug.visibility`, `request_id`);
- runs the patch via the existing **live** director API (`StageEditController` / `GameLoopDirector` move/rotate/flip/remove/place + `request_render_refresh`);
- runs the visibility probe **against the live session's on-screen viewport** (see B2);
- returns the same JSON response shape as Step A.

### 3.2 Live-viewport perception (B2) — the crux
The pixel-coverage + occlusion probe must read the **viewport the human sees**:
- read `get_viewport().get_texture().get_image()` of the **running game's active viewport** (the real operating-shift render on screen), **not** a newly-instantiated SubViewport;
- the hide-entity framebuffer-diff (Step A's proven mechanism) operates on that live texture;
- if the live render is unavailable (not in operating-shift, viewport not ready, headless) → top-level `verified=false`, honest reason — never fake green.

### 3.3 Flicker bound (B3) — the real tension
The hide-entity diff toggles target CanvasItems off for one capture. On the **live** view this risks a visible flash. Codex must do **one** of, and **state which**:
- **(a)** toggle within a single rendered frame the human cannot perceive (sub-frame restore), proven by measuring frames-visible-hidden ≤ 1 and reporting it; or
- **(b)** diff against a **copy** of the live viewport (snapshot the live texture, run hide-diff on an off-screen clone seeded from live state) — then **prove the clone is pixel-identical to the live render**, else it regresses to Step A's "not the human's render"; or
- **(c)** accept a bounded, logged flicker and report `flicker_frames` in the response so the cost is explicit.

**No-silent-cost rule:** any visual disturbance to the human MUST be reported in the JSON.

## 4. Acceptance — G-gate (extends F1–F5)

I re-run every check **independently, refute-first, reading the real render — not Codex's JSON**.

- **G1 live-viewport-grounded** — perception reads the human's actual viewport, not a probe SubViewport. *Falsifier I will run*: change a human-visible camera/zoom/pan state in the live session, re-query; reported `screen_area` MUST change accordingly. A fixed-camera probe-SubViewport implementation would NOT track this → fails G1.
- **G2 patch-via-host-visible** — a `world.patch` through the B1 host produces a human-visible change in the LIVE session (bbox move + pixel coverage > 0, before/after).
- **G3 no-green-but-inert end-to-end** — not in operating-shift / viewport unavailable / alpha-zero on the live render → `verified=false`, honest reason. I will force each case.
- **G4 flicker-bounded** — the B3 choice holds: either no perceptible flicker (frames-hidden ≤ 1, measured) or the flicker is reported in JSON. I inspect the response's flicker accounting and watch the live window.
- **G5 carry F2/F5** — still pixel-grounded (`screen_area` ≠ bbox; alpha-zero → 0), still no-screenshot (programmatic framebuffer read).

## 5. Task breakdown (Codex — CLAIM in #102 before starting)

- **SB0** — decide + state the control channel (TCP/socket/file) and the flicker strategy (B3 a/b/c). **Post the choice for my sign-off BEFORE building** (one cheap round-trip avoids a wrong-foundation rebuild, like T0 did).
- **SB1** — in-session host autoload behind a dev flag; same request/response contract as Step A.
- **SB2** — repoint the visibility probe to the live on-screen viewport; preserve hide-entity pixel-diff + geometric occlusion.
- **SB3** — flicker handling per SB0 choice + report `flicker_frames`.
- **SB4** — evidence: G1 (camera-state changes `screen_area`), G2 (live patch visible), G3 (3 forced not-verified cases), G4 (flicker accounting). Post DONE + commits + evidence; I run the G-gate.

## 6. Boundaries

- Dev/probe flag only; **NEVER** active in the shipped player build.
- Reuse Step A's proven mechanisms (hide-entity diff, geometric occlusion, save isolation slot 99); change only what B1–B3 require.
- No AB MCP surface, no `present()` wire, no nexus, no push to onsen `main` unless owner asks (Step C concerns).
- Implementation = Codex; design + G-gate acceptance = Claude. Independence preserved.
