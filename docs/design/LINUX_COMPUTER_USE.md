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
| `desktop_action` | **write** | wtype / wlrctl / ydotool / sway-IPC cursor | **coordinate** | `scripts/desktop_action.py` | `desktop_action/v1` | **by display** (nested `WAYLAND_DISPLAY` + sway-IPC abs cursor) |
| `desktop_invoke` | **write** | AT-SPI `Action.do_action` | **semantic** (zero coords) | `scripts/desktop_invoke.py` | `desktop_invoke/v0` | **by process** (target app PID ∈ `--cage-pid` subtree) |

The two read tools are a "look" pair (structure vs pixels); the two write tools are
an "act" pair (meaning vs coordinates). `desktop_invoke` is the input-side dual of
the bus-first read path: where `desktop_snapshot` *enumerates* AT-SPI accessibles,
`desktop_invoke` *activates* one by app/role/name with no screenshot and no OCR.

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

## 7. The deferred frontier — host-confirm

The four tools are complete and **isolated-only**. The next rung is the
**host-mutating confirm path**: making `desktop_action`/`desktop_invoke` reachable
against the *real* desktop behind a human-in-the-loop confirmation. The backend gate
already supports it (`--confirm --i-understand-this-touches-the-real-desktop`); what
is missing — deliberately — is the **confirm-UI surface** (terminal prompt? `notify`?
an interactive `present()` artifact?) and the product decision to open a boundary the
whole design has so far kept structurally closed. That is a product-level call, parked
until explicitly chosen.
