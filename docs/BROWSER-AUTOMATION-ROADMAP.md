# Browser Automation Roadmap — Closing the SaaS-Signup Gap

**Owner**: agent-bridge
**Started**: 2026-05-09
**Status**: Round 1 in progress

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

### Round 1 — foundation (started 2026-05-09)

Goal: turn the surface from "race-driven" into "debuggable".

- [ ] **#1 `browser_wait_for`** — selector / url / timeout_ms; built on
  `Page::wait_for_navigation` + JS polling fallback.
- [ ] **#5 stable `user_data_dir`** — read from `AGENT_BRIDGE_BROWSER_PROFILE`
  env (default `$HOME/.cache/agent-bridge/chrome-profile`). Stays per-PID
  only if the env var is unset *and* the dir is in use (Singleton lock check).
- [ ] **#10 eval error details** — capture `EvaluateReturnObject.exceptionDetails`
  and surface text + line/column + URL in the error message.
- [ ] **#2 `browser_list_pages` + new-tab tracking** — subscribe to
  `Target.targetCreated` and auto-insert into the `pages` map; new MCP
  tool returns `[{page, url, title}]`.

After Round 1, every `browser_*` interaction can be properly observed and
re-tried, and login state survives daemon restarts.

### Round 2 — sign-up main act

- [ ] #6 `browser_press_key`
- [ ] #7 `browser_select_option`
- [ ] #8 `browser_find_by_text` (a11y-tree match first, XPath fallback)
- [ ] #4 iframe scope flag on existing tools (`frame_url` / `frame_index`)

Target: 90% of pure-web sign-up forms reach the "API key shown" screen
without manual intervention.

### Round 3 — the hard cases

- [ ] #3 CAPTCHA pause/resume — issues a `notify`, blocks until
  `browser_resume(page)` is called.
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
