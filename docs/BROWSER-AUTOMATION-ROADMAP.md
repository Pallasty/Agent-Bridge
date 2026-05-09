# Browser Automation Roadmap — Closing the SaaS-Signup Gap

**Owner**: agent-bridge
**Started**: 2026-05-09
**Status**: Rounds 1 + 2 + 2.5 complete (2026-05-09); Round 3 #3 done; Round 3 #9 next

## Why this exists

The agent-bridge browser surface (7 MCP tools, all `Tier::Niche` behind
`AGENT_BRIDGE_TOOL_PROFILE=all`) is enough to read pages and click static
buttons, but cannot drive a SaaS sign-up flow end-to-end (race conditions,
OAuth pop-ups, CAPTCHA, iframes, lost session on restart). This document
catalogues every observed gap, ranks them by impact on the "API-key
signup" use case, and tracks attack rounds.

Source-of-truth code:
- `crates/browser/src/lib.rs` — `BrowserBackend` trait
- `crates/browser/src/chromium_cdp.rs` — chromiumoxide CDP backend
- `crates/bridge/src/mcp_tools.rs:860-1226` — 7 MCP tool wrappers

## Limitations catalogue

### P0 — directly blocks SaaS sign-up

| # | Gap | Blocks | Effort |
|---|-----|--------|--------|
| 1 | `browser_wait_for(selector \| url \| timeout_ms)` | every flow with form-submit → page-change | S |
| 2 | new-tab / OAuth-popup tracking + `browser_list_pages` | "Sign in with Google", payment redirect | M |
| 3 | CAPTCHA / 2FA pause-and-resume | reCAPTCHA, OTP email/SMS | M |
| 4 | iframe-scoped eval/click/fill_form | Stripe Elements, reCAPTCHA, Auth0 | M |
| 5 | persistent `user_data_dir` (currently per-PID) | every MCP restart wipes login | XS |

### P1 — needed for ~50% of flows

| # | Gap | Blocks | Effort |
|---|-----|--------|--------|
| 6 | `browser_press_key(Tab/Enter/Escape/...)` | Enter-to-submit, Esc-to-dismiss, Tab focus chain | S |
| 7 | proper `<select>` option setting | country / role / plan dropdowns | S |
| 8 | find element by visible text (a11y/XPath) | text-only buttons ("Sign Up", "Continue") | S |
| 9 | XHR response capture (Network domain) | API key delivered as a post-signup XHR JSON | M |
| 10 | eval error details (stack/line) | JS exceptions currently surface as one-line `Backend(...)` | S |

### P2 — nice-to-have

11. file upload (`<input type=file>`)
12. scroll / hover
13. element-scoped screenshot (currently full-page only)
14. UA / viewport / locale config
15. `browser_back / _forward / _reload`
16. expose `browser_close_page` MCP tool (trait method exists)

## Attack rounds

### Round 1 — foundation ✅ (2026-05-09)

Goal: turn the surface from "race-driven" into "debuggable".

- [x] **#1 `browser_wait_for`** (commit `da7343c`) — selector / url /
  timeout_ms; 100 ms poll via raw CDP `Runtime.evaluate`. Returns
  `{matched, elapsed_ms, current_url}`.
- [x] **#5 stable `user_data_dir`** (commit `0a80940`) — reads
  `AGENT_BRIDGE_BROWSER_PROFILE` env, defaults to
  `$HOME/.cache/agent-bridge/chrome-profile`. Login state survives daemon
  restart.
- [x] **#10 eval error details** (commit `0a80940`) — exceptions now
  surface as `evaluate exception @ <url>:<line>:<col>: <text>: <desc>`
  via a single `eval_with_exception_details` helper used by `eval`,
  `extract_text`, and `fill_form`.
- [x] **#2 `browser_list_pages` + new-tab discovery** (commit `506e9eb`)
  — on-demand reconciliation via `browser.pages()`; mints fresh page_ids
  for unknown targets and marks them `newly_tracked=true`. No event
  subscription yet — agent calls list_pages() after any click that
  might open a tab.

After Round 1: every `browser_*` interaction can be properly observed
and retried, login state survives daemon restarts, and OAuth pop-ups +
"open in new tab" links are addressable.

### Round 2 — sign-up main act (started 2026-05-09)

- [x] **#6 `browser_press_key`** (commits `baf217c` MCP wrapper, `86a666a`
  trait/impl fixup) — CDP `Input.dispatchKeyEvent` with named keys from
  `chromiumoxide::keys::USKEYBOARD_LAYOUT` + 4-bit modifier bitmask.
- [x] **#7 `browser_select_option`** (commits `07ccb00` wrapper, `303df01`
  trait/impl fixup) — eval-based `<select>` handler matching by value
  OR text label; dispatches input+change events.
- [x] **#8 `browser_find_by_text`** (commits `07ccb00` wrapper, `303df01`
  trait/impl fixup) — DOM scan + deepest-match filter + auto-generated
  CSS selector path; up to 5 candidates returned.
- [x] **#4 iframe scope** (commits `0f681fb` wrappers, `2335752`
  trait/impl fixup) — `browser_list_frames` (Page.getFrameTree
  flattened) + `browser_eval_in_frame` (Page.createIsolatedWorld →
  Runtime.evaluate with contextId). Crosses cross-origin boundaries;
  unblocks Stripe Elements / reCAPTCHA / Auth0 widgets.

R2 sign-up surface: ✅ 4 of 4 done.

Target: 90% of pure-web sign-up forms reach the "API key shown" screen
without manual intervention.

### Round 2.5 — fallout from R1+R2 live testing ✅ (2026-05-09)

Two issues surfaced when smoke-testing the R2 surface end-to-end. Both
landed same day:

- [x] **#5b SingletonLock self-heal** (commit `df30a39`) — `ensure_browser`
  now reads `<profile>/DevToolsActivePort` and tries
  `Browser::connect("http://127.0.0.1:<port>")` before launching. On
  successful connect + 500ms version probe, the new daemon adopts the
  orphan chrome from the previous daemon's session. If adoption fails
  (no port file / dead port / probe timeout), stale Singleton{Lock,
  Cookie,Socket} files are removed before launching fresh. Verified
  end-to-end after /mcp reconnect on 2026-05-09: navigate succeeds
  immediately, no manual kill+rm required.

- [x] **#4b cross-origin OOPIF — list_frames** (commits `7fa7f7a`,
  `6855eb1`) — browser-level `Target.getTargets` filtered to
  `type=="iframe"` appended with `kind:"oopif"`. Verified on 2026-05-09
  with `data:` parent + `https://example.com` iframe: count=3 (parent
  + example.com OOPIF + chrome new-tab OOPIF), parent_id linkage
  correct.
- [ ] **#4b cross-origin OOPIF — eval_in_frame** (PARTIAL, blocked) —
  `Target.attachToTarget(flatten=true)` succeeds and `browser.get_page`
  resolves a Page bound to the OOPIF, but `Runtime.evaluate` over the
  flatten session times out: chromiumoxide 0.9.1's `Page::execute`
  doesn't appear to route OOPIF responses back to awaiting futures
  even after explicit attach. Three fix paths: (a) fork chromiumoxide
  + upstream PR, (b) `Browser::connect` to the per-target
  webSocketDebuggerUrl as a separate Browser instance, (c) raw
  websocket CDP bypassing chromiumoxide. None feasible in one
  session. Same-origin / about:srcdoc iframes work via the
  `Page.createIsolatedWorld` path (verified earlier R2.4).

### Round 3 — the hard cases

- [x] **#3 CAPTCHA pause/resume** (commit `28d2798`, 2026-05-09) —
  `browser_pause_for_human(page, reason, hint?, timeout_ms?)` fires a
  `NotifyEvent` (severity=Attention, source=Mcp) via `Hub.deliver`
  *before* blocking, then awaits a `tokio::sync::oneshot` keyed by
  `page` in `ChromiumCdpBackend.pause_waiters`. `browser_resume(page)`
  removes the entry and sends `Resumed`. Outcome ∈ {resumed, timeout,
  superseded}; second pause on the same page supersedes the older
  waiter (no zombie hangs). `close()` also releases the waiter so a
  stranded request can't outlive its page. `timeout_ms` clamped to
  [1_000, 1_800_000].
- [ ] #9 `browser_capture_response(page, url_pattern, until_ms)` — start a
  CDP `Network.responseReceived` recorder; return all matching response
  bodies after a timeout or after `wait_for` resolves.

### Round 4 — completeness

- All P2 items.

## Cross-device sync

This document is in the repo and pushed to both GitLab + GitHub via the
`origin` multi-push remote, so Mac (office) + aio2 (home) both see the
same checklist after `git pull`. Status changes update this file *and*
the `project_browser_roadmap` memory record.
