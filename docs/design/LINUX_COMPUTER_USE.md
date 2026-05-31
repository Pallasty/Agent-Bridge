# Linux Computer Use — canonical lane reference

**Lane:** forum thread 79 · **Status:** four-tool family complete, isolated-only · **Last updated:** 2026-05-30

The desktop sibling of the `browser_*` and `mobile_*` MCP tool families: let an agent
*see* and *act on* a live Wayland/sway desktop. The guiding principle throughout is
**bus-first, vision-as-fallback** — prefer structured, semantic channels (compositor
IPC, AT-SPI) and drop to pixels/OCR only where no bus exposes the truth.

This document is the canonical map of what shipped, how isolation works, and where
the deliberately-closed boundary is. For per-tool detail read the script headers;
for history read the project memory `project_linux_computer_use_v0_v1_shipped_20260528`.

---

## 1. Capability matrix

| MCP tool | side | channel | grounding | backend script | schema | isolation primitive |
|---|---|---|---|---|---|---|
| `desktop_snapshot` | **read** | swaymsg outputs/tree + grim + AT-SPI | — | `scripts/desktop_snapshot.py` | `desktop_snapshot/v0.5` | read-only (no mutation, no gate) |
| `vision_grounding_ocr` | **read** | OCR over a screenshot region → (x,y) | pixels | `scripts/vision_grounding_ocr.py` | — | read-only |
| `desktop_verify` | **read** | AT-SPI + sway tree, polled to timeout → verdict + `recover` | semantic / window | `scripts/desktop_verify.py` | `desktop_verify/v0` | read-only; `--cage-pid`/`--swaysock` only *scope* presence |
| `desktop_action` | **write** | wtype / wlrctl / ydotool / sway-IPC cursor | **coordinate** | `scripts/desktop_action.py` | `desktop_action/v1` | **by display** (nested `WAYLAND_DISPLAY` + sway-IPC abs cursor) |
| `desktop_invoke` | **write** | AT-SPI `Action.do_action` | **semantic** (zero coords) | `scripts/desktop_invoke.py` | `desktop_invoke/v0` | **by process** (target app PID ∈ `--cage-pid` subtree) |

The three read tools are the "look + confirm" set (structure / pixels / *did it
work?*); the two write tools are the "act" pair (meaning vs coordinates).
`desktop_invoke` is the input-side dual of the bus-first read path: where
`desktop_snapshot` *enumerates* AT-SPI accessibles, `desktop_invoke` *activates* one
by app/role/name with no screenshot and no OCR, and `desktop_verify` *re-reads* one to
confirm the effect landed. All three read tools are in `codex-essential`; the two
mutating tools are not.

### Grounding ladder (verified on aio2 sway 1.11, kernel 7.0 / Ubuntu 26.04)

```
shell / CDP  >  swaymsg window-IPC (universal)  >  AT-SPI (GTK only)  >  vision / OCR
```

Climb as high as the target allows. A GTK button is best invoked semantically
(`desktop_invoke`); a terminal or a private-canvas app exposes no bus tree and must
be grounded by vision (`vision_grounding_ocr` → `desktop_action`).

---

## 2. Two isolation models — and why they differ

The two mutating tools isolate by **different primitives**, and this is not an
accident of implementation — it follows from how each channel is scoped.

### desktop_action — isolation **by display**

Input injection is display-scoped. A nested sway compositor owns its own
`WAYLAND_DISPLAY`; `wtype`/`wlrctl` target that display, and absolute cursor
positioning goes through **sway IPC** (`swaymsg seat … cursor set/press`) confined
to that nested compositor. This gives true isolation with **0px landing error** and
**no global `uinput`**. The backend refuses any sway socket bound to a physical
output (`DP-`/`HDMI-`/`eDP-`/…) so it can never leak onto the host desktop.

> `ydotool`/`uinput` absolute positioning is the exception: it drives the **real
> host seat globally** and *cannot* be confined to a nested display. It exists only
> for deliberate, gated host actions — never reachable via MCP (see §3).

### desktop_invoke — isolation **by process subtree**

AT-SPI is different: `org.a11y.Bus` is a **session-global D-Bus registry**. A
nested-cage GTK app and a host app register on the **same** bus. There is no
per-display or per-bus a11y namespace — so isolation **cannot** be by bus or
display. Instead it is **by process**: an invoke is isolated iff the target
accessible's application PID is a descendant of a nominated nested compositor
(`--cage-pid`, walked via `/proc/<pid>/stat` PPID chain). The tool runs in the host
environment (a11y is display-independent) and filters by process lineage.

This distinction (#1793, resolved empirically) is the single most important fact
about the lane: **you isolate input by where it goes, but you isolate AT-SPI by
whose process owns the accessible.**

---

## 3. isolated-only gate posture (the closed boundary)

Both mutating backends share one gate. An action is allowed iff **one** of:

- **(a) isolated** — `desktop_action`: nested `WAYLAND_DISPLAY` ≠ host; `desktop_invoke`: target app PID ∈ `--cage-pid` subtree; **or**
- **(b) host-acknowledged** — `--confirm` **and** `--i-understand-this-touches-the-real-desktop`; **or**
- **(c) dry-run** — logs intent, injects/invokes nothing.

Default (no flags) on the host = **DENIED**. Every call, allowed or denied, is
appended to a JSONL audit trail (`~/.cache/agent-bridge/desktop_{action,invoke}_audit.jsonl`),
ready to feed the event spine (thread 56).

**The MCP wrapper never passes (b).** It checks only for the isolation marker
(`cage_pid` for invoke, an isolated display for action) and refuses host mutation
with a structured error (`host_invoke_not_exposed` / equivalent) before ever
shelling out. So through MCP, host mutation is **structurally unreachable** — not
merely discouraged. The host path exists in the backend (for a deliberate,
human-driven future) but has no MCP surface. Neither tool is in
`CODEX_ESSENTIAL_DIRECT_EXTRAS`.

Crossing this boundary — exposing host mutation behind a human-in-the-loop confirm —
is the **deferred frontier** (§6): a product-level decision, not a code tweak.

---

## 4. AT-SPI toolkit boundary (the bus-first reliability map)

The bus-first path is only as wide as toolkits expose. Quantified on aio2:

| toolkit | snapshot (read tree) | semantic invoke | notes |
|---|---|---|---|
| **GTK3** | ✅ always | ✅ | `GTK_A11Y=atk-bridge` is the GTK3 spelling |
| **GTK4** | ✅ on by default | ✅ | **do NOT set `GTK_A11Y=atk-bridge`** — GTK4 rejects the unknown value and *suppresses* a11y. Also: GTK strips `_` from labels as a mnemonic marker, so `--ok-label=AB_OK` ⇒ accessible name `ABOK` |
| **Qt** | ⚠️ needs `org.a11y.Status.IsEnabled` flipped true (`--activate-a11y`) | (untested) | verified read live for Strawberry once flipped |
| **Electron** | ⚠️ needs `--force-renderer-accessibility` at launch | (untested) | verified for Cursor |
| **terminals / private canvas** | ❌ no tree | ❌ | fall back to vision/OCR |

Role names are matched as **substrings** (`--role button` catches both `"button"`
and `"push button"`), so the GTK3/GTK4 role-name drift does not bite the selector.

---

## 5. Building an isolated cage (empirical recipe)

Everything was validated in a **nested sway** acting as a disposable cage:

- `WLR_BACKENDS=wayland` nested sway → seat **caps=3** (pointer/keyboard reach
  clients; clicks land). `WLR_BACKENDS=headless` → **caps=0** (IPC cursor does not
  reach clients) — use the wayland backend for any input test.
- Address the nested sway via **`SWAYSOCK`** (`$XDG_RUNTIME_DIR/sway-ipc.$uid.$pid.sock`),
  **not** `WAYLAND_DISPLAY`. Setting `WAYLAND_DISPLAY` for `swaymsg` silently leaks
  to the host desktop.
- Spawn cage apps with `swaymsg exec` (child PID becomes a sway descendant ⇒
  satisfies the `desktop_invoke` PID-subtree isolation predicate). Pass the nested
  `WAYLAND_DISPLAY` explicitly to the spawned app.
- Defense-in-depth: abort if the nested sway ever binds a physical output.
- **Caveat — nondeterministic output scale.** The nested output size/scale varies
  run-to-run (e.g. 948×1034 ↔ 1908×2114). This makes **coordinate** grounding tests
  scale-fragile (a documented vision-side caveat) — but **semantic invoke is immune**
  because it carries no coordinates. This is the strongest argument for L2.

---

## 6. Acceptance harnesses (`scripts/desktop_accept/`)

| harness | proves | observable |
|---|---|---|
| `run_accept.sh` | `desktop_action` isolated absolute click | 0px landing error in nested sway |
| `run_grounding_accept.sh` | vision grounding e2e (fixture-tsv → grounding → action click) | click lands on ground-truth bbox center |
| `run_invoke_accept.sh` | `desktop_invoke` semantic activate (GTK3 toy) | toy records activation; gate A/B/C 8/8 |
| `run_realapp_accept.sh` | **four-tool family vs a REAL GTK4 app (zenity)** | the app's **native exit code** — unfakeable |

`run_realapp_accept.sh` is the lane's closing proof. It drives **zenity** (a real
third-party GTK4 dialog, not our toy) and uses the app's own exit semantics as an
observable we cannot fabricate:

- isolated invoke of the button named `INVOKEOK` → zenity exits **0**;
- isolated invoke of `INVOKECANCEL` → zenity exits **1**.

Changing only the *name* in the selector flips the app's native exit code — proving
**semantic precision**: L2 selects the *right* button by meaning, where a coordinate
click could only target a pixel. Host posture (no `--cage-pid`) is DENIED and leaves
the dialog untouched. Verdict: **10/10 checks, 3/3 runs stable** (per the N-round
majority-vote falsifier discipline).

---

## 7. host-confirm — SHIPPED (three paths above the closed default)

The host-mutating confirm path — making `desktop_action`/`desktop_invoke` reachable
against the *real* desktop behind a human-in-the-loop confirmation — is **shipped**.
Three paths, all keeping host mutation NON-inline, with the default still DENY. See
`docs/design/HOST_CONFIRM_PATH.md` for the full design + honest threat model.

| path | how | MCP surface |
|---|---|---|
| **A** two-phase token | `confirm_host:true` mints a single-use TTL token + pending record + screen notify (zero exec); `desktop_confirm(token)` is the only MCP path that touches the real desktop, after a human assents | `desktop_confirm` |
| **B** present approval card | `present_await_decision(summary, token)` renders an Approve/Reject card in the daemon browser, blocks on a human click read back from the DOM, then the caller proceeds to `desktop_confirm(token)` | `present_await_decision` |
| **C** pre-authorized grant | a human mints a scoped/TTL'd grant via `scripts/desktop_grant.py` (CLI only, never MCP); `use_grant:true` lets covered host actions skip per-call confirm inside the window | `use_grant` flag |

Honest threat model: on a box where the agent has a shell + browser eval, none of these
is an agent-proof sandbox. Their job is to keep host mutation deliberate and auditable
(single-use, TTL, scope, screen notify, JSONL audit) — to bound blast radius and defeat
*silent* mutation, not to defeat an adversarial agent.

---

## 8. The act loop — snapshot → act → verify → recover

The primitives compose into a closed loop; `desktop_verify` is the leg that closes it.
After an act it re-reads the bus and returns a `recover` hint that maps 1:1 to the next
move, so the caller reads ONE field instead of re-deriving intent from a fresh full
snapshot.

```
desktop_snapshot ─▶ pick target ─▶ desktop_invoke / desktop_action ─▶ desktop_verify
       ▲                                                                    │
       │            proceed ─▶ next step                                    │
       │            retry   ─▶ re-act, SAME selector  ◀────────────────────┤
       └──────────  replan  ─▶ re-snapshot + re-plan  ◀────────────────────┤
                    escalate ─▶ human / rethink       ◀────────────────────┘
```

### verify expectations (reuse the selector you just acted on)

| expect | holds when | typical act it confirms |
|---|---|---|
| `element_gone` | the AT-SPI selector no longer resolves | clicked a button that closes a dialog |
| `element_appeared` | the selector now resolves | opened a menu / dialog |
| `state_is` / `state_not` | the element has / lacks a state (checked, expanded, …) | toggled a checkbox |
| `window_gone` / `window_appeared` | a sway window matching app_id/pid/title is absent / present | closed / launched a window |
| `focus_is` | the focused window matches the selector | focus / activate |

### recover decision table

| verdict | change (needs before-fingerprint) | `recover` | next move |
|---|---|---|---|
| `verified` | — | `proceed` | effect landed; advance |
| `unmet` | `unchanged` (or no before) | `retry` | nothing moved → idempotent re-act, same selector |
| `unmet` | `diverged` | `replan` | state moved but not as expected → re-snapshot, re-plan |
| `error` | — | `escalate` | can't observe (AT-SPI down, bad selector) → human / rethink |

`change` is emitted only when a cheap before-fingerprint is supplied (`before_present`
for elements, `before_focus` for `focus_is`) — the caller already knows the before-state
of the one thing it is about to change, so it need not capture a whole before-snapshot.

### two hard-won constraints baked into the loop

1. **Always poll, never check once (settle).** GUIs animate; AT-SPI registration and
   window teardown lag the action by tens-to-hundreds of ms. `desktop_verify` polls to
   `poll_timeout_secs` and returns the instant the expectation holds (`held_after_ms`
   records when). A single check races the toolkit and yields a false `unmet`.

2. **The daemon's own browser fights host GUI apps on a tiling compositor.** When a
   `present()`-family card (path B `present_await_decision`) opens, it is a *headed*
   Chrome window on the same sway. sway tiles it in, reconfiguring sibling windows; a
   GTK4/Vulkan dialog (e.g. zenity) can lose its surface (`VK_ERROR_SURFACE_LOST_KHR`)
   and die — taking the pending host target with it *before* `desktop_confirm` runs.
   Mitigation, verified on aio2: **float the daemon card window** so it does not reflow
   the target — `swaymsg 'for_window [title="(?i)approve host"] floating enable'`. Any
   loop pairing the daemon browser with a host GUI target should float / isolate the
   daemon window (separate workspace or output) so the observer does not perturb the
   observed.

> Nested-cage caveat: a `WLR_BACKENDS=wayland` + pixman nested sway is unstable for
> GTK4/Vulkan clients (surface loss). For `desktop_invoke`/`desktop_verify` live checks,
> prefer the real GPU desktop + process-subtree (`--cage-pid`) scoping over a
> nested-display cage; the nested-display cage is for `desktop_action` coordinate
> isolation only.
